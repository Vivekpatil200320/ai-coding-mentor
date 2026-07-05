# ADR-0004: Zero-budget provider — NVIDIA free tier, model tiered per node

- **Status:** Accepted
- **Date:** 2026-07-01
- **Deciders:** Backend

## Context

The original spec named `claude-sonnet-4-6` via `langchain_anthropic`. There
is no budget for a paid API and no `ANTHROPIC_API_KEY` in this project, so
Claude would fail on the first call. The five agents have very different
reasoning demands: the router just classifies, the mentor/analysis/evaluation
need real code reasoning.

## Decision

All agents use `ChatNVIDIA` (NVIDIA's free-tier API Catalog) via a single
factory, `backend/agents/llm.py`. Model choice is tiered by need:

- **Router:** `meta/llama-3.1-8b-instruct` — cheap/fast, and usually not even
  called (reads `task_type` from metadata; LLM is a fallback).
- **Analysis / mentor / evaluation:** `meta/llama-3.1-70b-instruct`.

`llm.py` is the only place models are configured. A 120s client timeout is
set because the free tier is slow under load.

## Consequences

- **Positive:** the whole system runs at zero cost, which is the binding
  constraint.
- **Negative — capability ceiling:** open 70B models have weaker instruction
  hierarchy than frontier models. This is the root reason prompt injection
  can't be fully closed here (see `docs/security/sandbox-audit.md`) and why
  the evaluator can't rely on guaranteed structured output — `evaluation_agent`
  regex-extracts JSON and degrades gracefully rather than trusting the model
  to emit clean JSON.
- **Negative — free-tier reliability:** intermittent `SocketTimeoutError`s are
  expected weather, not bugs; this is the motivation for the retry
  recommendation in the orchestration review (O-6).
- **Cost still matters even at "free":** free-tier quota and latency are
  finite, so token hotspots are real (orchestration review O-7/O-8) — most
  notably the per-session analysis call that should be cached per challenge.

## Hard-won operational note

**Do not use `meta/llama-3.3-70b-instruct`.** It hangs until the client
timeout on the free tier (reproduced repeatedly during the build);
`llama-3.1-70b-instruct` is the same size class and responds in under a
second. This single wrong model ID once turned an 8-test run into a 10-minute
hang. The choice of the 3.1 variant is deliberate, not incidental.

## Alternatives considered

- **Anthropic / any paid API.** Out of scope — no budget.
- **Local Ollama.** Viable and truly unlimited, but caps quality to what the
  dev machine can run (≈7–14B) and adds an infra dependency; the hosted free
  tier gives 70B-class quality with no local compute. Revisit if free-tier
  limits bite.
