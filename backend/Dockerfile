FROM python:3.11-slim AS base

WORKDIR /app

RUN pip install --no-cache-dir uv

# Build context is the repo root (not backend/), because challenge_data.py
# resolves CHALLENGES_DIR as a sibling of backend/ (parents[2] from
# backend/agents/challenge_data.py) — the image needs both directories in
# that same relative layout, not just backend/'s own contents.
COPY backend/pyproject.toml backend/uv.lock ./
# --frozen: fail the build rather than silently drift from uv.lock.
# --no-install-project: app code isn't copied yet, nothing to install.
RUN uv sync --frozen --no-install-project --no-dev

COPY backend/. .
COPY challenges /challenges

EXPOSE 8000

# No --reload in production — reload's filesystem watcher is dev-only
# and needless overhead on a running container.
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
