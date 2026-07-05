"""slowapi rate limiting, keyed by user_id where available.

slowapi calls key_func synchronously (see slowapi/extension.py:
`limit_key = lim.key_func(request)`, no await) — an async key_func here
would never actually run; the coroutine object itself would silently
become the "key", making every request its own unique bucket and
defeating the rate limit entirely. That's a real bug this project hit
during verification, not a hypothetical.

Fix: UserIdExtractMiddleware (api/middleware.py) reads user_id out of
POST bodies up front — where an async read is fine — and stashes it on
request.state. This key_func then just reads it back synchronously.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def rate_limit_key(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"
    return get_remote_address(request)


limiter = Limiter(key_func=rate_limit_key)
