# ADR-0001: The compiled LangGraph is a design artifact; the API drives nodes directly

- **Status:** Accepted
- **Date:** 2026-07-01
- **Deciders:** Backend

## Context

The spec calls for a five-agent LangGraph orchestration
(router → analysis → mentor → execution → evaluation). `build_mentor_graph()`
in `backend/graph/mentor_graph.py` implements exactly that as a compiled
`StateGraph` with a `mentor → execution` edge, a conditional
`execution → {evaluation | mentor}` edge, and `interrupt_before=["execution"]`.

But the product is not a single autonomous pass. It is an interactive loop:
the user chats with the mentor **repeatedly** (each `/message` a separate
HTTP request over minutes), then submits code, possibly fails, chats more,
resubmits. The compiled graph does not model this:

- Its only mentor edge is `mentor → execution` — there is no
  `mentor → mentor` chat loop.
- Resuming a checkpointed graph after out-of-band chat turns would replay
  the `conversation_history` that existed when the graph paused at
  `interrupt_before`, not the turns exchanged since — i.e. stale state.

## Decision

Keep the compiled graph as the **design artifact and test target**, but
serve live traffic from `backend/api/orchestrator.py`, which calls the node
**functions** directly against the Supabase-persisted `MentorState`, one
bounded sequence per HTTP endpoint:

- `POST /sessions/start` → `router` → `analysis`
- `POST /sessions/{id}/message` → `mentor` (repeatable)
- `POST /sessions/{id}/submit` → `execution` → `evaluation` (pass) | `mentor` (fail)

The same node functions back both paths, so behavior stays defined in one
place (`backend/agents/`). The persisted state is the single source of truth,
not a graph checkpointer.

## Consequences

- **Positive:** the live path is loop-free by construction (see
  orchestration-review O-1); each request is a short acyclic sequence that
  reads current state and returns. No stale-checkpoint hazard. The interactive
  chat loop the product needs is expressible (`/message` repeats naturally).
- **Positive:** the graph still earns its keep — it is the readable spec of
  the intended flow (`draw_ascii()`), and node functions are unit-tested in
  isolation.
- **Negative / watch-outs:** two representations of the flow can drift. The
  edges in `orchestrator.py` must be kept in sync with the graph by hand.
  Node behaviors verified in isolation are not verified *as composed by the
  orchestrator* except via the API integration tests.
- **Constraint for the future:** do not move live traffic onto
  `graph.ainvoke()` without reintroducing a recursion limit + step cap — the
  graph's `mentor↔execution` cycle is only safe today because
  `interrupt_before` makes the human the pump.

## Alternatives considered

- **Drive everything through `graph.ainvoke()` with the checkpointer.**
  Rejected: the stale-`conversation_history`-on-resume problem, and modeling a
  repeatable chat turn inside the graph adds a self-loop + step guards for no
  benefit over calling the node.
- **Delete the graph, keep only the orchestrator.** Rejected: the graph is the
  clearest artifact of intended flow and keeps the node contracts honest.
