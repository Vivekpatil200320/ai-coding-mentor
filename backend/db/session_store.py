"""Supabase-backed session persistence, replacing api/session_store.py's
in-memory dict. Sessions, their chat messages, and their evaluation
reports now survive a backend restart.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from db.supabase_client import get_supabase_client
from graph.state import MentorState


@dataclass
class Session:
    id: str
    user_id: str
    challenge_id: str
    state: MentorState
    is_complete: bool
    passed: Optional[bool]


def _initial_state(session_id: str, challenge_id: str) -> MentorState:
    return {
        "session_id": session_id,
        "challenge_id": challenge_id,
        "user_code": "",
        "task_type": "bug_fix",  # placeholder; overwritten by router_node
        "codebase_analysis": "",
        "conversation_history": [],
        "hint_level": 0,
        "execution_result": {},
        "evaluation_report": {},
        "current_agent": "router",
        "is_complete": False,
    }


async def create_session(session_id: str, user_id: str, challenge_id: str) -> Session:
    state = _initial_state(session_id, challenge_id)
    client = await get_supabase_client()
    await client.table("sessions").insert(
        {
            "id": session_id,
            "user_id": user_id,
            "challenge_id": challenge_id,
            "state": state,
            "is_complete": False,
        }
    ).execute()
    return Session(
        id=session_id,
        user_id=user_id,
        challenge_id=challenge_id,
        state=state,
        is_complete=False,
        passed=None,
    )


async def get_session(session_id: str) -> Optional[MentorState]:
    try:
        uuid.UUID(session_id)
    except ValueError:
        # Not a valid UUID at all -- Postgres would reject the query
        # with a raw 22P02 error instead of just finding no rows, so
        # short-circuit to the same "not found" result a malformed ID
        # should produce.
        return None

    client = await get_supabase_client()
    response = (
        await client.table("sessions")
        .select("state")
        .eq("id", session_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]["state"]


async def get_session_owner(session_id: str) -> Optional[str]:
    """Cheap ownership check — used to reject requests for someone else's
    session before touching the (larger) state blob."""
    try:
        uuid.UUID(session_id)
    except ValueError:
        return None

    client = await get_supabase_client()
    response = (
        await client.table("sessions")
        .select("user_id")
        .eq("id", session_id)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]["user_id"]


async def update_session(session_id: str, state: MentorState) -> None:
    """Persists the full state blob and keeps the queryable top-level
    is_complete/passed columns in sync with it."""
    client = await get_supabase_client()
    execution_result = state.get("execution_result") or {}
    await client.table("sessions").update(
        {
            "state": state,
            "is_complete": bool(state.get("is_complete", False)),
            "passed": execution_result.get("passed"),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", session_id).execute()


async def save_message(session_id: str, role: str, content: str, hint_level: int) -> None:
    client = await get_supabase_client()
    await client.table("messages").insert(
        {
            "session_id": session_id,
            "role": role,
            "content": content,
            "hint_level": hint_level,
        }
    ).execute()


async def save_evaluation(session_id: str, scores: dict, report: dict) -> None:
    client = await get_supabase_client()
    await client.table("evaluations").insert(
        {
            "session_id": session_id,
            "scores": scores,
            "report": report,
        }
    ).execute()
