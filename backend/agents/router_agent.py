"""Router Agent — classifies task_type and initializes routing context.

task_type is authoritative in each challenge's metadata.json (set when the
challenge was authored), so the common path is a zero-cost, zero-latency
read — no reason to spend an LLM call reclassifying something already
known. The LLM classifier only runs as a fallback if metadata is missing
or malformed, so the router still degrades gracefully instead of crashing.
"""

from agents.challenge_data import load_broken_code, load_metadata
from agents.llm import ROUTER_MODEL, get_llm
from graph.state import MentorState
from observability.langfuse_setup import wrap_with_langfuse

_VALID_TASK_TYPES = {"bug_fix", "feature_extension", "refactor"}

_CLASSIFY_SYSTEM_PROMPT = (
    "You classify a coding challenge into exactly one category based on "
    "its starting code. Respond with only one word: bug_fix, "
    "feature_extension, or refactor. No punctuation, no explanation."
)


async def _classify_from_code(code: str) -> str:
    llm = get_llm(ROUTER_MODEL, temperature=0.0)
    response = await llm.ainvoke(
        [
            {"role": "system", "content": _CLASSIFY_SYSTEM_PROMPT},
            {"role": "user", "content": code},
        ]
    )
    guess = response.content.strip().lower()
    return guess if guess in _VALID_TASK_TYPES else "bug_fix"


@wrap_with_langfuse("router")
async def router_node(state: MentorState) -> dict:
    challenge_id = state["challenge_id"]

    try:
        metadata = load_metadata(challenge_id)
    except (FileNotFoundError, ValueError):
        metadata = {}

    task_type = metadata.get("type")
    if task_type not in _VALID_TASK_TYPES:
        code = state.get("user_code") or load_broken_code(challenge_id)
        task_type = await _classify_from_code(code)

    return {
        "task_type": task_type,
        "hint_level": 0,
        "current_agent": "analysis",
    }
