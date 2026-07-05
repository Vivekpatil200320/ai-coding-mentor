# Orchestration Review — Mentor Agent Graph

Systematic failure-mode analysis of the five-agent orchestration
(router, analysis, mentor, execution, evaluation). The decisions behind
the shape are recorded as ADRs in `docs/adr/`; this document is the
failure-mode analysis and findings.

**The one fact that reframes everything:** the compiled LangGraph in
`backend/graph/mentor_graph.py` does **not** serve live traffic.
`backend/api/orchestrator.py` drives the node *functions* directly, one
bounded sequence per HTTP endpoint. See [ADR-0001](adr/0001-graph-is-design-artifact-orchestrator-drives-nodes.md).
Both paths are analyzed below where they differ.

Findings are tagged **O-N**; severity **High / Medium / Low**.

---

## 1. Infinite routing loops

**Compiled graph:** there is a cycle — `mentor → execution → mentor`
(execution routes back to mentor on failure). It is **not** an autonomous
loop: `interrupt_before=["execution"]` pauses the graph before every
execution step and waits for the user to submit code again. The human is
the pump; each iteration requires a real submission. LangGraph's
`recursion_limit` is the backstop if that ever changed.

**Live path (orchestrator):** loops are **structurally impossible**. Each
endpoint runs a fixed, acyclic sequence and returns — `/message` runs the
mentor exactly once, `/submit` runs execution then exactly one of
evaluation/mentor. There is no edge that re-enters a node within a request.

**O-1 · Loop risk — Low (by construction).** No action. Boundedness comes
from the request/response shape, not from a recursion guard — worth keeping
in mind if anyone later moves live traffic onto `graph.ainvoke()`, which
would reintroduce the cycle and require a recursion limit + step cap.

---

## 2. State corruption across turns

State is the full `MentorState`, persisted as a Supabase `jsonb` blob. The
orchestrator pattern is read-modify-write: `get_session` → mutate dict →
`node → state.update(...)` → `update_session` writes the **whole** blob.

**O-2 · Concurrent writes lose updates — Medium.** Two overlapping requests
for the same session (e.g. a second `/message` before the first's final
`update_session`, or `/message` racing `/submit`) both read the same blob,
mutate, and write — last-writer-wins silently clobbers the other's
`conversation_history` / `hint_level` / `execution_result`. There is no
optimistic-concurrency check (no version / `updated_at` compare-and-set) and
no per-session lock. The `messages` and `evaluations` **rows** are
append-only so they survive, but the authoritative `state` blob can drop a
turn. Likelihood is low today (single dev user, no auth) but this is a real
sharp edge. *Fix when it matters:* serialize per session (advisory lock keyed
on `session_id`) or add optimistic concurrency on the `state` write.

**O-3 · Partial-failure inconsistency in `/submit` — Low.** On a pass,
`run_submit` inserts the `evaluations` row (`save_evaluation`) **before** the
final `update_session`. If the process dies between them, an evaluation row
exists but `state.is_complete` is still false, so `GET /report` returns 409.
Self-heals on resubmit (idempotent enough). Acceptable; documented so it
isn't mistaken for data loss.

**O-4 · `conversation_history` grows unbounded — Medium (cost, not
correctness).** Every turn appends and the entire history is (a) re-serialized
to `jsonb` on every write and (b) re-sent in every mentor prompt. See §5.

---

## 3. Sandbox timeout mid-graph

Handled cleanly. `run_code_in_sandbox` owns a 30s wall-clock timeout and, on
expiry, returns `SandboxResult(timed_out=True, passed=False)` after
force-removing the container (verified: no orphans). `execution_node` treats
not-passed uniformly, so a timeout becomes a normal "tests failed → route to
mentor" turn with `test_results` explaining the timeout. **No graph/state
corruption, no hang** — the timeout is enforced host-side and doesn't depend
on in-container cooperation.

**O-5 · Semaphore back-pressure is request latency, not failure — Low.**
`MAX_CONCURRENT_EXECUTIONS = 5`. A 6th concurrent `/submit` awaits the
semaphore; the HTTP request simply takes longer. Bounded and correct, but
worth noting that submit latency includes queueing under load.

---

## 4. Where retries belong

**Current state: no retries anywhere.** Every LLM call (`ainvoke`/`astream`),
Docker call, and Supabase call can transiently fail, and does — the
`aiohttp SocketTimeoutError` flakiness on NVIDIA's free tier is exactly this
class. Today a transient LLM failure propagates to a 500 (or an error frame
on the `/message` SSE stream).

**O-6 · Retries are missing and belong at the I/O boundary, not the
orchestration layer — Medium.** Retrying a whole node is wrong: nodes have
side effects (`save_message`, `save_evaluation`, appending to history), so a
node-level retry double-writes. Retries belong **around the individual
LLM/DB call**, where they can be made idempotent — e.g. a bounded
exponential-backoff wrapper on the LLM client in `agents/llm.py`, retrying
only on transport errors (timeouts, 5xx, connection resets), never on a
successful-but-unwanted response. Docker "daemon not up" is not
retry-recoverable and should surface as a clear operational error (it already
does, via the sanitized `_safe_docker_error`). *Recommendation, not yet
implemented.*

---

## 5. Token-cost hotspots

**O-7 · Analysis is recomputed per session but is deterministic per
challenge — High (cost).** `analysis_node` makes a **70B** call reading the
full `broken_code` on **every session start**. But its inputs
(`broken_code/main.py` + `metadata`) are identical for a given
`challenge_id` across all users and all sessions — the output is effectively
a per-challenge constant. Today it is paid fresh on every single session.
This is the largest avoidable cost in the system. *Fix:* precompute the
analysis once per challenge (build step or first-use cache keyed on
`challenge_id`) and read it from there; the node becomes a lookup. See
[ADR-0004](adr/0004-nvidia-free-tier-tiered-by-node.md) for why cost control
matters on this stack specifically.

**O-8 · Mentor re-sends full history + full analysis every turn — Medium
(cost).** Each mentor turn's prompt contains the entire
`conversation_history` **and** the `codebase_analysis` blob (in the system
prompt). NVIDIA's endpoints have **no prompt caching**, so every one of those
tokens is repaid on every turn — cost grows quadratically over a long
session (linear history × per-turn). Mitigations: cap/rolling-window the
history sent to the model, and/or summarize older turns. Not urgent at
current usage; flagged because it compounds with O-4.

**O-9 · Router is cheap by design — informational (good).** The router reads
`task_type` from `metadata.json` and only falls back to an **8B** LLM call if
metadata is missing. The common path spends zero LLM tokens. Keep this — it's
the right instinct applied in the right place.

**Evaluator** sends source + test output once per pass — bounded, one-shot,
not a hotspot.

---

## Summary of actionable findings

| ID | Severity | Finding | Status |
|----|----------|---------|--------|
| O-2 | Medium | Concurrent session writes lose updates (no locking / CAS) | Recommendation |
| O-6 | Medium | No retries; belong at the LLM/DB call boundary, idempotently | Recommendation |
| O-7 | High (cost) | Analysis recomputed per session though deterministic per challenge | Recommendation |
| O-8 | Medium (cost) | Mentor re-sends full history + analysis every turn (no caching) | Recommendation |
| O-1,3,5 | Low | Loop-free by construction; minor partial-failure & back-pressure notes | Accepted |

This review is analysis only — no orchestration code was changed. The
decisions that produced the current shape are recorded in `docs/adr/`.
