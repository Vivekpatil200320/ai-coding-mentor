# ADR-0005: Backend uses the Supabase service_role key; authorization lives in application code, not RLS

- **Status:** Accepted
- **Date:** 2026-07-05
- **Deciders:** Backend

## Context

0001's migration enabled RLS on `sessions`/`messages`/`evaluations` but gave
the `anon` role `USING (true) WITH CHECK (true)` on all of them — permissive
by design, tracked as a known gap pending real auth (Phase 9, never built).
Supabase's own advisor flags this (`rls_policy_always_true`) on all three
tables. Production-readiness review confirmed the practical exposure: the
anon key was never shipped to the browser (the frontend only calls FastAPI),
so this wasn't internet-exploitable — but it meant the *only* thing standing
between "public" and "full database read/write" was that one key staying
secret forever. That's a single point of failure, not a security boundary.

Separately, the API routes themselves had no ownership check: `/message`,
`/submit`, and `/report` verified a session existed but not that the caller's
`user_id` matched it. Anyone who obtained a session UUID (e.g. a shared
report link) could drive or read someone else's session.

## Decision

Two changes, applied together:

1. **`db/supabase_client.py` connects with `SUPABASE_SERVICE_ROLE_KEY`, not
   the anon key.** The backend is the only Supabase caller in this
   architecture — there is no scenario where a browser talks to Supabase
   directly — so there's no reason to route through RLS-constrained anon
   access at all. `0002_lock_down_rls.sql` drops the `anon_full_access_pre_auth`
   policies, so RLS now denies `anon`/`authenticated` entirely. `service_role`
   bypasses RLS by design, which is expected and fine: the key never leaves
   the server (it's in `.env`, gitignored, never a `NEXT_PUBLIC_*` var).
2. **`api/routes.py` checks `session_store.get_session_owner(session_id)`
   against the caller-supplied `user_id`** before touching a session's state,
   returning 403 on mismatch. This is the actual authorization boundary now
   — it was already the *intended* boundary implicitly, RLS was never really
   enforcing it since `user_id` isn't tied to `auth.uid()`.

## Consequences

- **Positive:** closes the single-point-of-failure gap without waiting on
  real auth. Database-level defense in depth is now "nothing gets in except
  this one server process," which is the correct shape for a backend-only
  access pattern.
- **Negative — this is still not real multi-user security.** `user_id` is a
  client-supplied string (`localStorage`, see `frontend/lib/api.ts`
  `getOrCreateUserId`) with no cryptographic identity behind it. Anyone can
  claim any `user_id` by editing localStorage or the request body directly.
  The ownership check stops casual cross-session access (e.g. a stale/shared
  report URL landing on someone else's session) — it does not stop a
  determined attacker from impersonating another `user_id` outright. Closing
  that requires real authentication (Supabase Auth + RLS keyed on
  `auth.uid()`), which is explicitly out of scope for this pass — see the
  "Everything including real auth" option that was deferred at the start of
  this remediation.
- **Neutral:** RLS policies now exist mostly as a backstop against a future
  bug (e.g. someone adding a second Supabase caller without thinking about
  this). They are not doing meaningful work today since `service_role`
  bypasses them.

## Alternatives considered

- **Session-variable-scoped RLS** (`set_config('request.user_id', ...)` per
  request, policy checks `current_setting`). Would let RLS do real
  per-session enforcement without waiting for auth. Rejected for this pass:
  requires an extra round-trip per request to set the config value reliably
  through Supabase's connection pooling, and still wouldn't be a real
  security boundary since the value is still just a client-supplied string —
  it would add complexity without closing the actual gap (spoofable
  identity). Revisit only if there's a reason to add a second Supabase
  caller before real auth lands.
- **Build real auth now.** Correct long-term answer, explicitly deferred —
  the user chose the pragmatic-hardening scope over the full-auth scope for
  this pass.
