"""Analysis Agent — builds an internal understanding of what's broken.

This agent's output is for the Mentor Agent's use, not the end user's. It
must never reveal the fix or write corrected code — only describe the
bug's nature and root cause richly enough for a Socratic mentor to guide
toward it without stating it outright.
"""

from agents.challenge_data import load_broken_code, load_metadata
from agents.llm import ANALYSIS_MODEL, get_llm
from graph.state import MentorState
from observability.langfuse_setup import wrap_with_langfuse

_SYSTEM_PROMPT = (
    "You are a senior engineer preparing to mentor someone through a code "
    "review conversation. You are not fixing this code yourself, and you "
    "must never write or reveal the corrected code anywhere in your "
    "analysis.\n\n"
    "Deeply analyze the codebase below. Identify:\n"
    "- what is broken, specifically\n"
    "- why it's broken (the underlying misconception or gap)\n"
    "- the general pattern or principle this bug tests\n\n"
    "Write this as private notes for yourself, the mentor — not as an "
    "explanation you'd show the learner directly. Do not include a "
    "corrected version of the code anywhere in your response."
)


@wrap_with_langfuse("analysis")
async def analysis_node(state: MentorState) -> dict:
    challenge_id = state["challenge_id"]
    metadata = load_metadata(challenge_id)
    code = load_broken_code(challenge_id)

    llm = get_llm(ANALYSIS_MODEL, temperature=0.2)
    user_prompt = (
        f"Challenge: {metadata.get('title', challenge_id)}\n"
        f"Learning objective: {metadata.get('learning_objective', 'unknown')}\n\n"
        f"Codebase (broken_code/main.py):\n```python\n{code}\n```"
    )
    response = await llm.ainvoke(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]
    )

    return {
        "codebase_analysis": response.content,
        "current_agent": "mentor",
    }
