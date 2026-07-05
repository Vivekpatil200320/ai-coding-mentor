FROM python:3.11-slim

RUN pip install --no-cache-dir pytest fastapi uvicorn httpx

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin sandbox

WORKDIR /workspace
RUN chown sandbox:sandbox /workspace

USER sandbox

# Network isolation (--network none) and resource limits (mem_limit,
# pids_limit) are enforced at container-create time by
# backend/sandbox/docker_runner.py, not here — a Dockerfile build always
# has network access regardless of how the resulting image is later run.
CMD ["python3", "-m", "pytest", "-v", "tests/"]
