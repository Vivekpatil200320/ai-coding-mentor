"""Drives the 5 agent nodes directly rather than through the compiled
StateGraph (backend/graph/mentor_graph.py).

Why not just call graph.ainvoke()? The compiled graph is checkpointed per
thread_id and pauses at interrupt_before=["execution"] — a clean fit for
a single linear pass, but this API needs a mentor<->user chat loop before
submission that the graph's single mentor->execution edge doesn't model.
Resuming a checkpointed graph after out-of-band chat turns would replay
the STALE conversation_history that existed when the graph originally
paused, not the messages exchanged since. So this module treats the
persisted session state (db/session_store.py, Supabase-backed as of
Phase 7) as the single source of truth and calls each node function
directly, replicating the same edges the graph encodes:

    start   -> router -> analysis                  (mentor speaks first
               on the client's first /message call, not here)
    message -> mentor                               (repeatable — the
               loop the graph doesn't have)
    submit  -> execution -> mentor   (if failed)
                          -> evaluation (if passed)

The compiled graph remains valid as the design artifact / ASCII diagram
and for the isolated node tests from Phase 3 — it's just not what serves
live traffic.

Every state mutation is written back via update_session, and every
conversation turn / evaluation also gets its own row (messages /
evaluations tables) for structured querying independent of the state
jsonb blob.
"""

from typing import AsyncIterator

from agents.analysis_agent import analysis_node
from agents.evaluation_agent import evaluation_node
from agents.execution_agent import execution_node
from agents.mentor_agent import mentor_node, stream_mentor_response
from agents.router_agent import router_node
from db import session_store
from graph.state import MentorState


async def run_start(session_id: str, user_id: str, challenge_id: str) -> MentorState:
    session = await session_store.create_session(session_id, user_id, challenge_id)
    state = session.state
    state.update(await router_node(state))
    state.update(await analysis_node(state))
    await session_store.update_session(session_id, state)
    return state


async def stream_message(session_id: str, message: str) -> AsyncIterator[str]:
    state = await session_store.get_session(session_id)
    if state is None:
        raise KeyError(session_id)

    state["conversation_history"] = list(state.get("conversation_history", [])) + [
        {"role": "user", "content": message}
    ]
    await session_store.save_message(session_id, "user", message, state.get("hint_level", 0))

    chunks: list[str] = []
    async for chunk in stream_mentor_response(state):
        chunks.append(chunk)
        yield chunk

    full_response = "".join(chunks)
    state["conversation_history"] = list(state["conversation_history"]) + [
        {"role": "assistant", "content": full_response}
    ]
    await session_store.save_message(
        session_id, "assistant", full_response, state.get("hint_level", 0)
    )
    await session_store.update_session(session_id, state)


async def run_submit(session_id: str, code: str) -> MentorState:
    state = await session_store.get_session(session_id)
    if state is None:
        raise KeyError(session_id)

    state["user_code"] = code
    state.update(await execution_node(state))

    execution_result = state.get("execution_result") or {}
    if execution_result.get("passed"):
        state.update(await evaluation_node(state))
        report = state.get("evaluation_report") or {}
        await session_store.save_evaluation(session_id, report.get("scores", {}), report)
    else:
        history_before = len(state.get("conversation_history", []))
        state.update(await mentor_node(state))
        history_after = state.get("conversation_history", [])
        if len(history_after) > history_before:
            latest = history_after[-1]
            await session_store.save_message(
                session_id,
                latest.get("role", "assistant"),
                latest.get("content", ""),
                state.get("hint_level", 0),
            )

    await session_store.update_session(session_id, state)
    return state
