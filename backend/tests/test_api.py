"""Integration tests against the real API — real NVIDIA LLM calls, real
Docker sandbox execution, real LangFuse traces. No mocking, consistent
with how the rest of this project has been tested (Phase 2's sandbox
tests hit real Docker, Phase 4's hit real LangFuse). Expect these to be
slow (each agent call is a real model round-trip) and to consume a small
amount of free-tier NVIDIA quota.
"""

import json
import uuid
from pathlib import Path

import httpx
import pytest

from main import app

CHALLENGES_DIR = Path(__file__).resolve().parents[2] / "challenges"


def _read_challenge_code(challenge_id: str, variant: str) -> str:
    return (CHALLENGES_DIR / challenge_id / variant / "main.py").read_text()


async def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )


async def _start_session(client: httpx.AsyncClient, challenge_id: str = "challenge_01") -> dict:
    user_id = f"test-user-{uuid.uuid4().hex[:8]}"
    response = await client.post(
        "/sessions/start",
        json={"challenge_id": challenge_id, "user_id": user_id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    body["user_id"] = user_id
    return body


async def test_start_session():
    async with await _client() as client:
        body = await _start_session(client)

    assert body["challenge"]["id"] == "challenge_01"
    assert body["challenge"]["type"] == "bug_fix"
    assert "session_id" in body and body["session_id"]
    assert "USERS[user_id]" in body["codebase"]


async def test_send_message_streams_tokens():
    async with await _client() as client:
        session = await _start_session(client)
        session_id = session["session_id"]

        async with client.stream(
            "POST",
            f"/sessions/{session_id}/message",
            json={"user_id": session["user_id"], "message": "I think the bug is in the dict access"},
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")

            events = []
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    events.append(line[len("data: "):])

    assert events[-1] == "[DONE]"
    token_events = [json.loads(e) for e in events[:-1]]
    assert len(token_events) > 0
    assert all("token" in e for e in token_events)


async def test_submit_passing_code():
    async with await _client() as client:
        session = await _start_session(client)
        session_id = session["session_id"]

        code = _read_challenge_code("challenge_01", "solution")
        response = await client.post(
            f"/sessions/{session_id}/submit", json={"user_id": session["user_id"], "code": code}
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["execution_result"]["passed"] is True
    assert body["next_action"] == "evaluation"


async def test_submit_failing_code():
    async with await _client() as client:
        session = await _start_session(client)
        session_id = session["session_id"]

        code = _read_challenge_code("challenge_01", "broken_code")
        response = await client.post(
            f"/sessions/{session_id}/submit", json={"user_id": session["user_id"], "code": code}
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["execution_result"]["passed"] is False
    assert body["next_action"] == "mentor"


async def test_get_report_after_passing():
    async with await _client() as client:
        session = await _start_session(client)
        session_id = session["session_id"]

        code = _read_challenge_code("challenge_01", "solution")
        await client.post(
            f"/sessions/{session_id}/submit", json={"user_id": session["user_id"], "code": code}
        )

        response = await client.get(
            f"/sessions/{session_id}/report", params={"user_id": session["user_id"]}
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("parse_error") is not True
    assert body["scores"]


async def test_get_report_before_passing_is_409():
    async with await _client() as client:
        session = await _start_session(client)
        session_id = session["session_id"]

        response = await client.get(
            f"/sessions/{session_id}/report", params={"user_id": session["user_id"]}
        )

    assert response.status_code == 409


async def test_unknown_session_is_404():
    async with await _client() as client:
        response = await client.post(
            "/sessions/does-not-exist/submit",
            json={"user_id": "test-user", "code": "x = 1"},
        )

    assert response.status_code == 404


async def test_wrong_user_id_is_403():
    async with await _client() as client:
        session = await _start_session(client)
        session_id = session["session_id"]

        message_response = await client.post(
            f"/sessions/{session_id}/message",
            json={"user_id": "someone-else", "message": "hi"},
        )
        submit_response = await client.post(
            f"/sessions/{session_id}/submit",
            json={"user_id": "someone-else", "code": "x = 1"},
        )
        report_response = await client.get(
            f"/sessions/{session_id}/report", params={"user_id": "someone-else"}
        )

    assert message_response.status_code == 403
    assert submit_response.status_code == 403
    assert report_response.status_code == 403


async def test_health_and_challenges():
    async with await _client() as client:
        health = await client.get("/health")
        challenges = await client.get("/challenges/")

    assert health.status_code == 200
    body = health.json()
    assert body["status"] == "ok"
    assert body["sandbox"] in ("ok", "error")
    assert body["langfuse"] in ("ok", "error")

    assert challenges.status_code == 200
    ids = [c["id"] for c in challenges.json()]
    assert {"challenge_01", "challenge_02", "challenge_03"}.issubset(set(ids))
