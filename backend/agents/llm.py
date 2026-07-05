"""Shared LLM client factory for all five agents.

Zero-budget stack: NVIDIA's free-tier API Catalog instead of Claude (see
the project's earlier architecture decision — no ANTHROPIC_API_KEY exists
in this project). Model choice is tiered by how much reasoning depth each
agent's job actually needs:

- router:     cheap/fast — classification only, and only a fallback path
- analysis:   needs real code reasoning — largest free-tier model
- mentor:     the product's core voice — largest free-tier model
- evaluation: rubric judgment — largest free-tier model
"""

import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_nvidia_ai_endpoints import ChatNVIDIA

load_dotenv()

ROUTER_MODEL = "meta/llama-3.1-8b-instruct"
# meta/llama-3.3-70b-instruct hangs for the full request timeout on
# NVIDIA's free tier as of this build (confirmed: consistent
# ReadTimeout at 120s across repeated calls) — llama-3.1-70b-instruct is
# the same size class and responded in under a second in the same test,
# so it's the one actually in use, not a downgrade for speed's sake.
ANALYSIS_MODEL = "meta/llama-3.1-70b-instruct"
MENTOR_MODEL = "meta/llama-3.1-70b-instruct"
EVALUATION_MODEL = "meta/llama-3.1-70b-instruct"


# Kept generous even though llama-3.1-70b-instruct has been fast in
# testing — NVIDIA's free tier can still be slow under load generally.
REQUEST_TIMEOUT_SECONDS = 120


@lru_cache(maxsize=None)
def get_llm(model: str, temperature: float = 0.2) -> ChatNVIDIA:
    return ChatNVIDIA(
        model=model,
        api_key=os.environ.get("NVIDIA_API_KEY"),
        temperature=temperature,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
