import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

load_dotenv()

from api.middleware import UserIdExtractMiddleware  # noqa: E402
from api.rate_limit import limiter  # noqa: E402
from api.routes import router  # noqa: E402

app = FastAPI(title="AI Coding Mentor API")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(UserIdExtractMiddleware)

# CORS_ALLOWED_ORIGINS overrides the localhost defaults for real deploys
# (comma-separated). 3000 per the original spec; 3001 because this dev
# environment already has an unrelated project's server bound to 3000.
_default_origins = "http://localhost:3000,http://localhost:3001"
allowed_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", _default_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
