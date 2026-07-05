"""In-memory session-level metric tracking.

No persistent store exists yet in this project, so this tracks the
current process's live sessions in memory. When a session ends, its
rollup is pushed to LangFuse via create_score, so the metrics survive
even though this module's in-memory state doesn't survive a restart.

Score naming: the summary score is named f"session_summary:{challenge_id}"
rather than a flat "session_summary" filtered by trace tags. Each of the
5 agent nodes opens its own span via wrap_with_langfuse — there's no
single overarching per-session trace yet (that would need the API layer,
a later phase) — so a session-level score created via session_id alone
isn't reliably attached to one specific tagged trace. Encoding challenge_id
directly into the score name sidesteps that and makes eval_dashboard's
queries an exact, unambiguous filter.
"""

import time
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv
from langfuse import get_client

load_dotenv()

SUMMARY_SCORE_PREFIX = "session_summary"


@dataclass
class SessionMetrics:
    session_id: str
    challenge_id: str
    started_at: float = field(default_factory=time.monotonic)
    ended_at: Optional[float] = None
    hints_requested: int = 0
    code_submissions: int = 0
    passed: Optional[bool] = None
    gave_up: bool = False
    final_scores: dict = field(default_factory=dict)

    @property
    def duration_seconds(self) -> float:
        end = self.ended_at if self.ended_at is not None else time.monotonic()
        return round(end - self.started_at, 2)


_sessions: dict[str, SessionMetrics] = {}


def start_session(session_id: str, challenge_id: str) -> SessionMetrics:
    metrics = SessionMetrics(session_id=session_id, challenge_id=challenge_id)
    _sessions[session_id] = metrics
    return metrics


def record_hint_requested(session_id: str) -> None:
    metrics = _sessions.get(session_id)
    if metrics is not None:
        metrics.hints_requested += 1


def record_code_submission(session_id: str) -> None:
    metrics = _sessions.get(session_id)
    if metrics is not None:
        metrics.code_submissions += 1


def record_gave_up(session_id: str) -> None:
    metrics = _sessions.get(session_id)
    if metrics is not None:
        metrics.gave_up = True


def end_session(session_id: str, passed: bool, final_scores: dict) -> Optional[SessionMetrics]:
    """Finalize a session and push its rollup to LangFuse as a score."""
    metrics = _sessions.get(session_id)
    if metrics is None:
        return None

    metrics.ended_at = time.monotonic()
    metrics.passed = passed
    metrics.final_scores = final_scores

    client = get_client()
    client.create_score(
        name=f"{SUMMARY_SCORE_PREFIX}:{metrics.challenge_id}",
        value=1.0 if passed else 0.0,
        data_type="BOOLEAN",
        session_id=session_id,
        comment=(
            f"hints={metrics.hints_requested} submissions={metrics.code_submissions} "
            f"duration={metrics.duration_seconds}s gave_up={metrics.gave_up}"
        ),
        metadata={
            "challenge_id": metrics.challenge_id,
            "hints_requested": metrics.hints_requested,
            "code_submissions": metrics.code_submissions,
            "duration_seconds": metrics.duration_seconds,
            "gave_up": metrics.gave_up,
            "final_scores": final_scores,
        },
    )
    client.flush()
    return metrics


def get_session_metrics(session_id: str) -> Optional[SessionMetrics]:
    return _sessions.get(session_id)
