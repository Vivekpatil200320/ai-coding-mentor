# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An AI coding mentor: users get dropped into an intentionally broken FastAPI codebase (a "challenge") and a Socratic mentor agent guides them to the fix through questions, never answers. Passing code gets a rubric-scored "senior engineer code review." Stack: FastAPI + LangGraph backend, Next.js 15 frontend, Docker sandbox for untrusted code execution, Supabase persistence, LangFuse observability.

## Commands

Backend (Python 3.11, uv-managed, `package = false` — app, not a library):

```bash
cd backend
uv sync                                        # install deps
uv run uvicorn main:app --reload --port 8000   # run API
uv run python -m pytest tests/test_sandbox.py -v   # sandbox tests (needs Docker + built image)
uv run python -m pytest tests/test_api.py -v       # API integration tests (SLOW, see below)
uv run python -m pytest tests/test_api.py::test_start_session -v   # single test
```

Sandbox image (must exist before any code execution works):

```bash
docker build -t coding-mentor-sandbox ./sandbox/   # from repo root
```

Frontend (Next.js 15 App Router, hand-rolled, no create-next-app):

```bash
cd frontend
npm install
npm run dev    # port 3000 by default; this dev machine runs it on 3001 (see below)
```

Dev-environment quirks:
- **Docker Desktop must be running** before sandbox tests, `/submit`, or `/health` shows `sandbox: ok`. It is frequently not running; `open -a Docker` and poll `docker info`.
- The preview tool's `launch.json` lives at the *session root* (`Desktop/Claude code/.claude/launch.json`), not in this repo. Entries: `ai-coding-mentor-backend` (8000), `ai-coding-mentor-frontend` (3001 — port 3000 is held by an unrelated project). Backend CORS defaults to allowing both 3000 and 3001 (see `CORS_ALLOWED_ORIGINS` below).
- Secrets live in root `.env` (gitignored via `.env*` with `!.env.example`). Keys: `NVIDIA_API_KEY`, `LANGFUSE_*`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (not the anon key — see Persistence below), `CORS_ALLOWED_ORIGINS` (optional, comma-separated, defaults to the two localhost ports above), `NEXT_PUBLIC_API_URL` (frontend build-time only).

### Deploying

`docker-compose.prod.yml` builds locked, multi-stage, non-dev images (no bind mounts, no `--reload`) for both services. **The sandbox's Docker-socket requirement rules out most serverless/PaaS hosts** — this needs a host that exposes `/var/run/docker.sock` (a VM, a Docker-capable host, etc.), not Vercel/Render's standard tier/Heroku-style platforms. See ADR-0006 for the full reasoning and what does/doesn't work. `NEXT_PUBLIC_API_URL` must be passed as a build arg (it's baked into the client bundle, not read at container start).

## Testing philosophy

No mocking anywhere. `tests/test_api.py` makes real NVIDIA LLM calls, real Docker container runs, real Supabase writes, real LangFuse traces. Full API suite takes ~8–10 minutes and consumes free-tier quota. Intermittent `aiohttp SocketTimeoutError` failures are NVIDIA free-tier flakiness, not app bugs — rerun the failed tests before investigating. `tests/test_sandbox.py` verifies the fail/pass/timeout/security-scan paths against challenge_01's real files.

## Architecture — the parts that aren't obvious from file names

### The compiled LangGraph does NOT serve traffic

`backend/graph/mentor_graph.py` builds the 5-node StateGraph (router → analysis → mentor → execution → evaluation, with execution→mentor loop-back and `interrupt_before=["execution"]`). It's kept as the design artifact and for graph-shape tests. **Live traffic goes through `backend/api/orchestrator.py`, which calls the node functions directly** against persisted session state. Reason: the API needs a repeatable mentor↔user chat loop before submission that the graph's single mentor→execution edge doesn't model, and resuming a checkpointed graph after out-of-band chat would replay stale `conversation_history`. If you change agent behavior, the node functions in `backend/agents/` are the single source of truth for both paths.

Flow mapping (orchestrator): `/sessions/start` → router + analysis (mentor does NOT speak here); `/sessions/{id}/message` → mentor (streaming); `/sessions/{id}/submit` → execution → evaluation (pass) or mentor (fail). The frontend sends a silent kickoff message on workspace load so the mentor appears to open the conversation.

### LLM provider: NVIDIA free tier, not Anthropic

Zero-budget constraint. All agents use `ChatNVIDIA` via `backend/agents/llm.py` — the only place models are configured. Router uses `meta/llama-3.1-8b-instruct`; analysis/mentor/evaluation use `meta/llama-3.1-70b-instruct`. **Do not switch back to `meta/llama-3.3-70b-instruct`**: it hangs until timeout on the free tier (verified repeatedly). Router reads `task_type` from challenge metadata first; its LLM call is only a fallback.

Because open models lack Anthropic-style guaranteed structured output, `evaluation_agent.py` regex-extracts JSON from the response and degrades to `{"parse_error": true, "raw_response": ...}` rather than crashing.

### Hint levels are rendered, not decided

`hint_level` (0=guiding question, 1=directional, 2=names the concept, 3=full explanation) lives in `MentorState`. `mentor_agent.py` only *renders* the style for the current level — nothing anywhere escalates it yet. Level 3 is supposed to require the user explicitly saying they're stuck. It's also persisted per-message to Supabase but never exposed in any API response (the SSE stream is tokens only).

### Sandbox (`backend/sandbox/docker_runner.py`)

Ported from the CyberRescue project's patterns: semaphore-capped concurrency (5), sanitized error messages (never leak Docker/host paths to callers), hard asyncio timeouts. Uses docker-py (fully sync) via `asyncio.to_thread`. Non-obvious details:

- Containers run `--network none`, non-root, mem/pids-limited — so **all challenge deps must be baked into the sandbox image**; there is no pip install at runtime.
- The user's code + the challenge's real test file are injected via an in-memory tar (`put_archive`), with a sandbox-specific `conftest.py` swapped in (the challenge's own conftest assumes a `broken_code/` sibling dir that doesn't exist in `/workspace`).
- Timeout path: the worker thread can't be killed, so `_force_remove_container` reaches in by container name and force-removes it, which unblocks the orphaned thread. Cleanup is verified — no leaked containers even on timeout.
- `validate_sandbox_security` is a regex denylist (subprocess, sockets, eval/exec, writes outside /workspace…) run **before** any container starts; violations refuse execution entirely. It's defense-in-depth, not the security boundary.

### Persistence (`backend/db/`)

Supabase project `ai-coding-mentor` (`atthrowpnlxxqtnsqhbj`, ap-southeast-2). Tables: `sessions` (full `MentorState` as jsonb + queryable `is_complete`/`passed` columns), `messages`, `evaluations`. Migration SQL is checked into `backend/db/migrations/` but was applied via the Supabase MCP — keep both in sync.

- **The backend connects with `SUPABASE_SERVICE_ROLE_KEY`, not the anon key** — it's the only Supabase caller in this architecture (the frontend only ever talks to FastAPI), so it bypasses RLS entirely rather than routing through it. RLS is enabled but has **no policies** for `anon`/`authenticated` (`0002_lock_down_rls.sql` dropped the old permissive ones) — deny-by-default for everyone except this one server process. Ownership is enforced in application code instead: `api/routes.py` compares the caller's `user_id` against `session_store.get_session_owner()` before touching a session, returning 403 on mismatch. See ADR-0005 for why. **Do not revert to the anon key or re-add a permissive `USING (true)` policy** — that was the actual gap this closed.
- There is still no real auth (`user_id` is a client-supplied string, not `auth.uid()`) — the ownership check stops stale/shared session links from working across users, it does not stop someone from deliberately claiming another `user_id`. Real auth is a Phase 9 follow-up, not done.
- `db/supabase_client.py` caches the async client **per event loop**, not as a plain singleton — a loop-bound client breaks with `ssl.SSLWantReadError` when pytest-asyncio's per-test loops touch it. Don't "simplify" this back to a module global.
- `get_session` / `get_session_owner` validate UUID format before querying (malformed ids must 404, not throw Postgres 22P02).
- Supabase query API caps `limit` at 100 (400 above that, not clamped).

### Observability (`backend/observability/`)

langfuse 4.x — the OTel-based SDK. The v2 API (`client.trace()`, `client.span()`) does not exist; use `get_client()`, `propagate_attributes()`, `start_as_current_observation()`. All 5 agent nodes are wrapped by `wrap_with_langfuse`, which logs **sanitized metadata only — never raw user code or chat text** (lengths, booleans, scores). Keep that invariant. The mentor's *streaming* path (`stream_mentor_response`) is untraced; only `mentor_node` is. `session_tracker` pushes a `session_summary:{challenge_id}` score on session end; `eval_dashboard` queries those back for pass-rate/avg-hints metrics.

### Rate limiting

slowapi calls `key_func` **synchronously** — an async key_func silently becomes a per-request coroutine object and defeats the limit entirely. Hence `api/middleware.py` (`UserIdExtractMiddleware`) pre-reads `user_id` from POST bodies onto `request.state`, and `api/rate_limit.py`'s key func reads it back sync. Don't make the key func async.

### Challenges (`challenges/challenge_0N/`)

Each has `metadata.json` (authoritative `task_type`), `broken_code/`, `solution/` (hidden from users), `tests/test_solution.py`, `rubric.json` (5 weighted dimensions incl. `what_senior_would_catch`). Invariant that must hold for every challenge: **tests fail on `broken_code`, pass on `solution`** — verify both directions when adding one. The analysis agent reads `broken_code` and is prompted to never emit corrected code; the evaluation agent scores against `rubric.json`.

### Frontend (`frontend/`)

Design tokens in `app/globals.css` — warm editorial system (ochre accent, `pass`/`fail` reserved for functional states only), Fraunces (`font-display`, the mentor's "voice" and headlines) + Hanken Grotesk (`font-sans`, UI/body) + IBM Plex Mono (`font-mono`, code only) via `next/font`. `lib/api.ts` hand-parses the SSE stream from `/message` (`data: {"token": ...}` frames, `data: [DONE]` terminator) because EventSource can't POST. Monaco theme in `components/CodeEditor.tsx` mirrors the CSS tokens. `NEXT_PUBLIC_API_URL` defaults to `http://localhost:8000` (must be set at Docker build time in prod, see Deploying above — it's inlined into the client bundle, not read at runtime).

`getOrCreateUserId()` persists a random UUID in `localStorage` and every mutating call (`/message`, `/submit`, `/report`) now sends it — required by the backend's ownership check (see Persistence above). The report page reads it from a `?user_id=` query param on the link, falling back to the browser's own id if navigated to directly.
