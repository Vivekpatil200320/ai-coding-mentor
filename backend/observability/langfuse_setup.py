"""LangFuse observability wiring for the agent graph.

SDK note: this project has langfuse 4.x installed, which is the newer
OpenTelemetry-based SDK — the v2 `Langfuse().trace()` API this phase was
originally described with no longer exists. The client auto-reads
LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY / LANGFUSE_HOST from the
environment (LANGFUSE_HOST is the deprecated alias for LANGFUSE_BASE_URL,
still supported) via get_client(), so no explicit key-passing is needed.

Every agent call is wrapped with wrap_with_langfuse(), which opens a span
tagged with session_id and challenge_id, records latency, and logs a
*sanitized* summary of the input state and the node's returned state
update — never raw user code or full conversation text.
"""

import functools
import time
from typing import Awaitable, Callable, TypeVar

from dotenv import load_dotenv
from langfuse import get_client, propagate_attributes

load_dotenv()

F = TypeVar("F", bound=Callable[..., Awaitable[dict]])


def _sanitize_input(state: dict) -> dict:
    """Structural metadata only — never the raw code or chat text."""
    return {
        "session_id": state.get("session_id"),
        "challenge_id": state.get("challenge_id"),
        "task_type": state.get("task_type"),
        "hint_level": state.get("hint_level"),
        "conversation_length": len(state.get("conversation_history") or []),
        "has_execution_result": bool(state.get("execution_result")),
    }


def _sanitize_output(update: dict) -> dict:
    """Log state *changes*, still sanitized — lengths and flags, not content."""
    sanitized: dict = {}
    for key in ("task_type", "hint_level", "current_agent", "is_complete"):
        if key in update:
            sanitized[key] = update[key]

    if "execution_result" in update:
        execution_result = update["execution_result"] or {}
        sanitized["passed"] = execution_result.get("passed")
        sanitized["timed_out"] = execution_result.get("timed_out")
        sanitized["refused"] = execution_result.get("refused")

    if "codebase_analysis" in update:
        sanitized["codebase_analysis_length"] = len(update["codebase_analysis"] or "")

    if "conversation_history" in update:
        sanitized["conversation_length"] = len(update["conversation_history"] or [])

    if "evaluation_report" in update:
        report = update["evaluation_report"] or {}
        scores = report.get("scores", {})
        sanitized["dimension_scores"] = {
            dim: info.get("score")
            for dim, info in scores.items()
            if isinstance(info, dict)
        }

    return sanitized


def wrap_with_langfuse(agent_name: str) -> Callable[[F], F]:
    """Decorator factory: traces one agent node call as a LangFuse span.

    Tags the span with session_id and challenge_id, records latency, and
    logs sanitized (metadata-only) versions of the input state and the
    node's returned state update. Never logs raw user code.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(state: dict, *args, **kwargs) -> dict:
            client = get_client()
            session_id = state.get("session_id", "unknown")
            challenge_id = state.get("challenge_id", "unknown")

            with propagate_attributes(
                session_id=session_id,
                tags=[agent_name, f"challenge:{challenge_id}"],
                metadata={"challenge_id": challenge_id, "agent_name": agent_name},
            ):
                start = time.monotonic()
                with client.start_as_current_observation(
                    name=agent_name,
                    as_type="span",
                    input=_sanitize_input(state),
                ) as span:
                    try:
                        result = await func(state, *args, **kwargs)
                    except Exception as exc:
                        span.update(level="ERROR", status_message=str(exc))
                        raise

                    latency_ms = round((time.monotonic() - start) * 1000, 2)
                    span.update(
                        output=_sanitize_output(result),
                        metadata={"latency_ms": latency_ms},
                    )
                    return result

        return wrapper  # type: ignore[return-value]

    return decorator


def test_langfuse_connection() -> None:
    """Verify LangFuse credentials work and a trace round-trips.

    Run: uv run python -c "from observability.langfuse_setup import
    test_langfuse_connection; test_langfuse_connection()"
    """
    client = get_client()

    if not client.auth_check():
        print(
            "LangFuse connection FAILED — check LANGFUSE_PUBLIC_KEY, "
            "LANGFUSE_SECRET_KEY, and LANGFUSE_HOST in .env"
        )
        return

    with client.start_as_current_observation(
        name="connection_test", as_type="span", input={"check": "startup"}
    ) as span:
        span.update(output={"status": "ok"})
        trace_id = client.get_current_trace_id()

    client.flush()

    trace_url = client.get_trace_url(trace_id=trace_id) if trace_id else None
    print(f"LangFuse connected. Trace visible at {trace_url or 'cloud.langfuse.com'}")
