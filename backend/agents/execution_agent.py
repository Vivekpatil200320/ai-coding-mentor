"""Execution Agent — runs the user's code in the sandbox and routes on the result.

Always runs the security check first; a violation refuses execution
outright (no container is ever started) and routes back to the mentor
with the refusal context instead of running untrusted code.
"""

from graph.state import MentorState
from observability.langfuse_setup import wrap_with_langfuse
from sandbox.docker_runner import run_code_in_sandbox, validate_sandbox_security


@wrap_with_langfuse("execution")
async def execution_node(state: MentorState) -> dict:
    user_code = state["user_code"]

    security = await validate_sandbox_security(user_code)
    if not security.safe:
        return {
            "execution_result": {
                "passed": False,
                "refused": True,
                "violations": security.violations,
                "stdout": "",
                "stderr": "",
                "test_results": "Execution refused: submitted code failed the security check.",
            },
            "current_agent": "mentor",
        }

    result = await run_code_in_sandbox(user_code, state["challenge_id"])
    execution_result = result.model_dump()
    execution_result["refused"] = False

    return {
        "execution_result": execution_result,
        "current_agent": "evaluation" if result.passed else "mentor",
    }


def route_after_execution(state: MentorState) -> str:
    """Conditional-edge path function: execution -> evaluation | mentor."""
    execution_result = state.get("execution_result") or {}
    return "evaluation" if execution_result.get("passed") else "mentor"
