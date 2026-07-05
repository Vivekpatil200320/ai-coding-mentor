# ADR-0002: Inter-agent communication is state-passing only, never tool calls

- **Status:** Accepted
- **Date:** 2026-07-01
- **Deciders:** Backend

## Context

Multi-agent systems commonly let agents invoke each other as tools — the
mentor could call an "analyze" tool, evaluation could call the sandbox as a
tool, etc. LangGraph supports this. The alternative is that every agent is a
pure function of the shared state: it reads fields from `MentorState`, does
its work, and returns a partial state update; no agent calls another.

## Decision

Every agent is a node that reads and returns `MentorState` fields. No agent
invokes another agent, and no agent uses LLM tool-calling to hand off. The
router writes `task_type`; analysis writes `codebase_analysis`; the mentor
reads `codebase_analysis` + `conversation_history` and appends a turn;
execution writes `execution_result`; evaluation reads those and writes
`evaluation_report`. Hand-off is data in the state, not a call.

## Consequences

- **Positive — observability:** each node is a single, discrete LLM (or
  sandbox) call wrapped by `wrap_with_langfuse`. A trace is a flat, legible
  sequence of node spans, not a nested tree of tool-call-within-tool-call. The
  "production observability" story (per-node latency, cost, pass-rate
  dashboards) depends on this flatness.
- **Positive — determinism & testability:** a node is `state → partial state`.
  It can be unit-tested with a hand-built state dict and no orchestration
  harness (this is how the Phase 3 node tests work).
- **Positive — no nested agent loops:** tool-calling agents can recurse into
  each other; pure state-passing nodes cannot. Combined with ADR-0001 this is
  why the live path has no loop risk.
- **Negative:** the orchestrator (or graph) must explicitly sequence nodes and
  thread state; there is no emergent "agent decides who to call next." That
  coordination logic lives in `orchestrator.py`, by design.

## Alternatives considered

- **Tool-calling hand-offs.** Rejected for this product: it trades legible,
  flat traces and deterministic nodes for emergent routing we don't need — the
  flow is fixed and known, so explicit sequencing is simpler and more
  observable.
