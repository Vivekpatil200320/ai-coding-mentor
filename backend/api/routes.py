"""REST + SSE API for the AI Coding Mentor.

See api/orchestrator.py for why /message drives mentor_node directly
instead of resuming the compiled LangGraph graph.
"""

import json
import uuid

import docker
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langfuse import get_client

from agents.challenge_data import list_challenges, load_broken_code, load_metadata
from api import orchestrator
from api.models import (
    ChallengeMetadata,
    EvaluationReport,
    ExecutionResult,
    HealthResponse,
    MessageRequest,
    StartSessionRequest,
    StartSessionResponse,
    SubmitRequest,
    SubmitResponse,
)
from api.rate_limit import limiter
from db import session_store

router = APIRouter()


@router.post("/sessions/start", response_model=StartSessionResponse)
@limiter.limit("10/minute")
async def start_session(request: Request, body: StartSessionRequest) -> StartSessionResponse:
    try:
        metadata = load_metadata(body.challenge_id)
        codebase = load_broken_code(body.challenge_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Unknown challenge_id: {body.challenge_id!r}")

    session_id = str(uuid.uuid4())
    await orchestrator.run_start(session_id, body.user_id, body.challenge_id)

    return StartSessionResponse(
        session_id=session_id,
        challenge=ChallengeMetadata(**metadata),
        codebase=codebase,
    )


@router.post("/sessions/{session_id}/message")
@limiter.limit("10/minute")
async def send_message(request: Request, session_id: str, body: MessageRequest) -> StreamingResponse:
    owner = await session_store.get_session_owner(session_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if owner != body.user_id:
        raise HTTPException(status_code=403, detail="Session belongs to a different user")

    async def event_stream():
        try:
            async for chunk in orchestrator.stream_message(session_id, body.message):
                yield f"data: {json.dumps({'token': chunk})}\n\n"
        except KeyError:
            yield f"data: {json.dumps({'error': 'Session not found'})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/submit", response_model=SubmitResponse)
@limiter.limit("10/minute")
async def submit_code(request: Request, session_id: str, body: SubmitRequest) -> SubmitResponse:
    owner = await session_store.get_session_owner(session_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if owner != body.user_id:
        raise HTTPException(status_code=403, detail="Session belongs to a different user")

    try:
        state = await orchestrator.run_submit(session_id, body.code)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")

    execution_result = state.get("execution_result") or {}
    next_action = "evaluation" if execution_result.get("passed") else "mentor"

    return SubmitResponse(
        execution_result=ExecutionResult(**execution_result),
        next_action=next_action,
    )


@router.get("/sessions/{session_id}/report", response_model=EvaluationReport)
async def get_report(session_id: str, user_id: str) -> EvaluationReport:
    owner = await session_store.get_session_owner(session_id)
    if owner is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if owner != user_id:
        raise HTTPException(status_code=403, detail="Session belongs to a different user")

    state = await session_store.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if not state.get("is_complete"):
        raise HTTPException(
            status_code=409,
            detail="Report not available yet — the session hasn't passed evaluation.",
        )

    return EvaluationReport(**(state.get("evaluation_report") or {}))


@router.get("/challenges/")
async def get_challenges() -> list[ChallengeMetadata]:
    return [ChallengeMetadata(**metadata) for metadata in list_challenges()]


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    sandbox_status = "ok"
    try:
        docker.from_env().ping()
    except Exception:
        sandbox_status = "error"

    langfuse_status = "ok"
    try:
        if not get_client().auth_check():
            langfuse_status = "error"
    except Exception:
        langfuse_status = "error"

    return HealthResponse(status="ok", sandbox=sandbox_status, langfuse=langfuse_status)
