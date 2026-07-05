-- Drops the pre-auth "anon can do anything" policies from 0001.
--
-- The backend has always been the only Supabase caller (the frontend
-- only ever talks to FastAPI, never to Supabase directly), so it now
-- connects with the service_role key, which bypasses RLS entirely.
-- Dropping the anon/authenticated policies here means RLS denies
-- everyone else by default — the service_role key never leaving the
-- server is the actual boundary; this just removes the second door
-- that was standing open next to it.
--
-- Per-session ownership (does this user_id own this session_id) is
-- enforced in application code (api/routes.py, session_store.get_session_owner)
-- because it isn't tied to auth.uid() yet — there's still no Supabase
-- Auth. Real auth-based RLS policies are a Phase 9 follow-up, not this one.
drop policy if exists "anon_full_access_pre_auth" on public.sessions;
drop policy if exists "anon_full_access_pre_auth" on public.messages;
drop policy if exists "anon_full_access_pre_auth" on public.evaluations;
