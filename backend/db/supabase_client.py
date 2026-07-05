"""Supabase client initialization.

No Supabase Auth yet (Phase 9) — user_id is just a string the frontend
passes, not tied to auth.uid(). The backend is the ONLY thing that ever
talks to Supabase (the frontend only calls the FastAPI backend), so it
connects with the service_role key and RLS is locked down to deny
anon/authenticated entirely (see db/migrations/0002_lock_down_rls.sql).
Ownership is enforced in application code instead — api/routes.py checks
the caller's user_id against session_store.get_session_owner() before
touching a session. That's the real authorization boundary; RLS here
just guarantees nothing OTHER than this backend can read/write these
tables, since the service_role key never leaves the server.

The client is cached per event loop, not just once globally: a plain
module-level singleton breaks across event loop boundaries (its
underlying HTTP connections/SSL sockets belong to whatever loop created
it), which surfaces as ssl.SSLWantReadError the moment a second loop
tries to use it. In a running FastAPI app there's only ever one loop for
the process's lifetime, so this never recreates in practice — it only
matters for test suites like pytest-asyncio's default of a fresh loop
per test, which is exactly how this was caught.
"""

import asyncio
import os

from dotenv import load_dotenv
from supabase import AsyncClient, create_async_client

load_dotenv()

_client: AsyncClient | None = None
_client_loop: asyncio.AbstractEventLoop | None = None


async def get_supabase_client() -> AsyncClient:
    global _client, _client_loop
    current_loop = asyncio.get_running_loop()
    if _client is None or _client_loop is not current_loop:
        _client = await create_async_client(
            os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        )
        _client_loop = current_loop
    return _client
