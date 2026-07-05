"""Docker sandbox execution layer for running user-submitted challenge code.

Ports the CyberRescue MCP server's Docker execution patterns
(/Users/vivekpatil/Projects/cyberrescue): bounded concurrency via an
asyncio semaphore, sanitized error messages that never leak host/socket
paths back to the caller, and hard async timeouts around blocking Docker
calls. CyberRescue used python-on-whales; this uses the official Docker
SDK (`docker`) per this project's requirements, so every blocking call is
wrapped in `asyncio.to_thread` since docker-py has no native async API.
"""

import asyncio
import io
import logging
import re
import tarfile
import uuid
from pathlib import Path

import docker
from docker.errors import DockerException, NotFound
from pydantic import BaseModel

logger = logging.getLogger("docker_runner")

SANDBOX_IMAGE = "coding-mentor-sandbox"
CHALLENGES_DIR = Path(__file__).resolve().parents[2] / "challenges"

MAX_CONCURRENT_EXECUTIONS = 5
_execution_semaphore = asyncio.Semaphore(MAX_CONCURRENT_EXECUTIONS)

CONTAINER_MEM_LIMIT = "256m"
CONTAINER_PIDS_LIMIT = 64
# 0.5 of a core, in billionths (docker-py `nano_cpus`). Without this a
# `while True: pass` submission pegs a full core for the entire timeout,
# and MAX_CONCURRENT_EXECUTIONS of them peg that many cores — a host DoS
# that mem_limit/pids_limit don't bound.
CONTAINER_NANO_CPUS = 500_000_000
# A size-bounded /tmp. Note we deliberately do NOT set read_only=True on
# the rootfs: Docker's put_archive (how the code is delivered into
# /workspace) refuses to extract into a read-only-rootfs container, so
# the two are mutually exclusive. Fully bounding disk would mean
# switching code delivery to a read-only bind mount + read_only rootfs —
# see docs/security/sandbox-audit.md (finding E-2) for that follow-up.
CONTAINER_TMPFS = {"/tmp": "size=64m,mode=1777"}

# Injected as tests/conftest.py inside the sandbox. The real challenge
# conftest.py assumes a broken_code/ sibling directory that doesn't exist
# in the sandbox's flat /workspace layout (just main.py + tests/), so we
# always swap in this minimal version instead.
_SANDBOX_CONFTEST = (
    "import sys\n"
    "from pathlib import Path\n\n"
    "sys.path.insert(0, str(Path(__file__).parent.parent))\n"
)

# Defense-in-depth static scan, not a substitute for container isolation.
# Purely textual pattern matching — it can be evaded by obfuscation, but
# it catches the straightforward cases before they ever reach a container.
_DANGEROUS_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("subprocess call", re.compile(r"\bsubprocess\.\w+\(")),
    ("subprocess import", re.compile(r"^\s*(import\s+subprocess\b|from\s+subprocess\s+import)", re.MULTILINE)),
    ("os.system call", re.compile(r"\bos\.system\(")),
    ("os.popen call", re.compile(r"\bos\.popen\(")),
    ("filesystem write outside /workspace", re.compile(r"""open\(\s*['"](/(?!workspace)|\.\./)""")),
    ("raw network socket usage", re.compile(r"\bsocket\.socket\(")),
    ("socket import", re.compile(r"^\s*(import\s+socket\b|from\s+socket\s+import)", re.MULTILINE)),
    ("outbound HTTP call", re.compile(r"\b(requests|httpx|urllib\.request)\.(get|post|put|delete|patch|urlopen)\(")),
    ("dangerous import: ctypes", re.compile(r"^\s*(import\s+ctypes\b|from\s+ctypes\s+import)", re.MULTILINE)),
    ("dynamic code execution", re.compile(r"\b(eval|exec)\(")),
    ("shell=True usage", re.compile(r"shell\s*=\s*True")),
]


class SandboxResult(BaseModel):
    passed: bool
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    test_results: str


class SecurityCheckResult(BaseModel):
    safe: bool
    violations: list[str]


def _safe_docker_error(context: str, exc: Exception) -> RuntimeError:
    """Log the real exception internally; never leak raw Docker errors
    (host paths, socket paths) back to the caller."""
    logger.error("Docker error during %s: %s", context, exc)
    return RuntimeError(
        f"Sandbox execution failed during {context}. See server logs for details."
    )


def _build_workspace_tar(code: str, test_source: str) -> bytes:
    """Build an in-memory tar archive laying out /workspace/main.py and
    /workspace/tests/{conftest.py,test_solution.py}."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        for name, content in (
            ("main.py", code),
            ("tests/conftest.py", _SANDBOX_CONFTEST),
            ("tests/test_solution.py", test_source),
        ):
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _load_challenge_tests(challenge_id: str) -> str:
    test_path = CHALLENGES_DIR / challenge_id / "tests" / "test_solution.py"
    if not test_path.is_file():
        raise ValueError(f"Unknown challenge_id: {challenge_id!r}")
    return test_path.read_text()


def _remove_container_quietly(container) -> None:
    try:
        container.remove(force=True)
    except DockerException as exc:
        logger.error("Failed to clean up sandbox container %s: %s", container.name, exc)


def _force_remove_container(container_name: str) -> None:
    """Best-effort cleanup for the timeout path.

    The background thread running `_run_container_sync` can't be killed
    directly — it's a Python thread blocked in a library call, not a
    subprocess we can signal — so on timeout we reach in and stop its
    container by name from the event loop instead. That unblocks the
    orphaned thread's `container.wait()` call, which then exits on its own.
    """
    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
    except NotFound:
        return
    except DockerException as exc:
        logger.error("Failed to look up timed-out container %s: %s", container_name, exc)
        return
    _remove_container_quietly(container)


def _run_container_sync(
    code: str, challenge_id: str, container_name: str
) -> tuple[int, bytes, bytes]:
    """Blocking Docker SDK work: create, populate, run, collect, clean up.

    Runs on a worker thread via asyncio.to_thread — the Docker SDK for
    Python has no native async API.
    """
    client = docker.from_env()
    test_source = _load_challenge_tests(challenge_id)
    tar_bytes = _build_workspace_tar(code, test_source)

    container = client.containers.create(
        SANDBOX_IMAGE,
        # -p no:cacheprovider + PYTHONDONTWRITEBYTECODE keep pytest from
        # writing .pytest_cache / __pycache__, so a read-only rootfs
        # doesn't break the run.
        command=["python3", "-m", "pytest", "-v", "--tb=short", "-p", "no:cacheprovider", "tests/"],
        name=container_name,
        network_disabled=True,
        user="sandbox",
        working_dir="/workspace",
        environment={"PYTHONDONTWRITEBYTECODE": "1"},
        mem_limit=CONTAINER_MEM_LIMIT,
        pids_limit=CONTAINER_PIDS_LIMIT,
        nano_cpus=CONTAINER_NANO_CPUS,
        # Untrusted code needs zero Linux capabilities and must never gain
        # privileges via setuid binaries. Dropping ALL caps + no-new-privileges
        # shrinks the kernel-attack surface well below the default.
        cap_drop=["ALL"],
        security_opt=["no-new-privileges:true"],
        tmpfs=CONTAINER_TMPFS,
    )
    try:
        container.put_archive("/workspace", tar_bytes)
        container.start()
        result = container.wait()
        exit_code = result.get("StatusCode", -1)
        stdout = container.logs(stdout=True, stderr=False)
        stderr = container.logs(stdout=False, stderr=True)
        return exit_code, stdout, stderr
    finally:
        _remove_container_quietly(container)


async def run_code_in_sandbox(
    code: str,
    challenge_id: str,
    timeout_seconds: int = 30,
) -> SandboxResult:
    """Run `code` against a challenge's test suite inside an isolated,
    network-disabled Docker container.

    Hard-caps execution at `timeout_seconds` and always cleans up the
    container, whether it finishes normally, times out, or errors.
    """
    container_name = f"coding-mentor-sandbox-{uuid.uuid4().hex[:12]}"

    async with _execution_semaphore:
        try:
            exit_code, stdout_bytes, stderr_bytes = await asyncio.wait_for(
                asyncio.to_thread(_run_container_sync, code, challenge_id, container_name),
                timeout=timeout_seconds,
            )
        except asyncio.TimeoutError:
            await asyncio.to_thread(_force_remove_container, container_name)
            return SandboxResult(
                passed=False,
                stdout="",
                stderr="",
                exit_code=-1,
                timed_out=True,
                test_results=f"Execution exceeded the {timeout_seconds}s timeout and was terminated.",
            )
        except DockerException as exc:
            raise _safe_docker_error("container execution", exc) from None

    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    return SandboxResult(
        passed=exit_code == 0,
        stdout=stdout,
        stderr=stderr,
        exit_code=exit_code,
        timed_out=False,
        test_results=stdout,
    )


async def validate_sandbox_security(code: str) -> SecurityCheckResult:
    """Static scan for patterns that shouldn't appear in sandboxed
    challenge code: subprocess/os.system calls, filesystem writes outside
    /workspace, network calls, and dangerous module imports.

    This is defense-in-depth on top of container isolation (no network,
    non-root user, no host mounts) — not a replacement for it.
    """
    violations = [
        description
        for description, pattern in _DANGEROUS_PATTERNS
        if pattern.search(code)
    ]
    return SecurityCheckResult(safe=len(violations) == 0, violations=violations)
