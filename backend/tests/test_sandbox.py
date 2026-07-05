from pathlib import Path

from sandbox.docker_runner import run_code_in_sandbox, validate_sandbox_security

CHALLENGES_DIR = Path(__file__).resolve().parents[2] / "challenges"


def _read_challenge_code(challenge_id: str, variant: str) -> str:
    return (CHALLENGES_DIR / challenge_id / variant / "main.py").read_text()


async def test_correct_code_passes():
    code = _read_challenge_code("challenge_01", "solution")
    result = await run_code_in_sandbox(code, "challenge_01")
    assert result.passed is True
    assert result.timed_out is False


async def test_broken_code_fails():
    code = _read_challenge_code("challenge_01", "broken_code")
    result = await run_code_in_sandbox(code, "challenge_01")
    assert result.passed is False
    assert result.timed_out is False


async def test_timeout_is_enforced():
    hanging_code = "while True:\n    pass\n"
    result = await run_code_in_sandbox(hanging_code, "challenge_01", timeout_seconds=5)
    assert result.timed_out is True
    assert result.passed is False


async def test_subprocess_call_is_flagged():
    code = "import subprocess\nsubprocess.run(['ls'])\n"
    result = await validate_sandbox_security(code)
    assert result.safe is False
    assert any("subprocess" in v for v in result.violations)
