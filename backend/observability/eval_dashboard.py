"""Read-side observability queries — aggregate metrics pulled back out of LangFuse.

These three functions are what actually gets pasted into a README or
demoed in an interview: pass rate and average hints-to-pass are computed
from the session_summary:<challenge_id> scores that
session_tracker.end_session() pushes to LangFuse, not from a local
database (there isn't one yet).

Pagination note: get_many() is capped at limit=100 by the API itself
(a limit above 100 is a 400, not silently clamped) and these functions
only read the first page — fine at this project's scale, would need
real pagination (looping on page= until a short page comes back) at
production traffic volume.
"""

from dotenv import load_dotenv
from langfuse import get_client
from langfuse.api.commons.errors.not_found_error import NotFoundError

from observability.session_tracker import SUMMARY_SCORE_PREFIX

load_dotenv()

_QUERY_LIMIT = 100


async def get_session_stats(session_id: str) -> dict:
    """Full stats for one session: its traces plus its final summary score.

    A session only exists in LangFuse once at least one trace references
    its session_id — a session that ended with a summary score but no
    traces (shouldn't happen via the real agent graph, but is possible if
    session_tracker is driven directly) 404s on the session lookup rather
    than erroring the whole call.
    """
    client = get_client()

    try:
        session = client.api.sessions.get(session_id)
        trace_count = len(session.traces)
    except NotFoundError:
        trace_count = 0

    scores_response = client.api.scores.get_many(
        session_id=session_id, limit=_QUERY_LIMIT
    )
    summary_scores = [
        score
        for score in scores_response.data
        if score.name.startswith(f"{SUMMARY_SCORE_PREFIX}:")
    ]
    latest_summary = summary_scores[-1] if summary_scores else None

    return {
        "session_id": session_id,
        "trace_count": trace_count,
        "passed": bool(latest_summary.value) if latest_summary else None,
        "metadata": latest_summary.metadata if latest_summary else None,
        "comment": latest_summary.comment if latest_summary else None,
    }


async def get_challenge_pass_rate(challenge_id: str) -> float:
    """Fraction of completed sessions for this challenge that passed."""
    client = get_client()

    scores_response = client.api.scores.get_many(
        name=f"{SUMMARY_SCORE_PREFIX}:{challenge_id}", limit=_QUERY_LIMIT
    )
    scores = scores_response.data
    if not scores:
        return 0.0

    passed_count = sum(1 for score in scores if score.value)
    return round(passed_count / len(scores), 4)


async def get_avg_hints_before_pass(challenge_id: str) -> float:
    """Average hints_requested across sessions for this challenge that passed."""
    client = get_client()

    scores_response = client.api.scores.get_many(
        name=f"{SUMMARY_SCORE_PREFIX}:{challenge_id}", limit=_QUERY_LIMIT
    )
    scores = scores_response.data

    passed_hint_counts = [
        (score.metadata or {}).get("hints_requested", 0)
        for score in scores
        if score.value
    ]
    if not passed_hint_counts:
        return 0.0

    return round(sum(passed_hint_counts) / len(passed_hint_counts), 2)
