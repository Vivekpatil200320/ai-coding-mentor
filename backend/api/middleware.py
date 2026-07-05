"""Reads user_id out of POST bodies up front so the (synchronous)
slowapi key function (api/rate_limit.py) can rate-limit by user
identity instead of just remote address.

Safe to read the body here and let it flow to FastAPI's own Pydantic
parsing afterward — Starlette caches the raw bytes on first read, so
downstream body reads (including FastAPI's request-body dependency
resolution) get the same cached bytes rather than re-reading the socket.
"""

import json

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class UserIdExtractMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST":
            body = await request.body()
            if body:
                try:
                    parsed = json.loads(body)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict) and parsed.get("user_id"):
                    request.state.user_id = parsed["user_id"]
        return await call_next(request)
