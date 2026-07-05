-- Applied to the ai-coding-mentor Supabase project (region ap-southeast-2)
-- via the Supabase MCP `apply_migration` tool. Checked in here for
-- reproducibility per the phase spec ("create via Supabase dashboard
-- first, then add migration SQL here").

create table public.sessions (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  challenge_id text not null,
  state jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  is_complete boolean not null default false,
  passed boolean
);

create table public.messages (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  hint_level int not null default 0,
  created_at timestamptz not null default now()
);

create table public.evaluations (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.sessions(id) on delete cascade,
  scores jsonb not null default '{}'::jsonb,
  report jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index messages_session_id_idx on public.messages (session_id);
create index evaluations_session_id_idx on public.evaluations (session_id);

-- RLS is enabled, but policies are deliberately permissive for the anon
-- role: there's no Supabase Auth yet (user_id is just a string the
-- frontend passes, not tied to auth.uid()). Real auth + per-user scoped
-- policies come in Phase 9 -- tighten these then instead of leaving RLS
-- off entirely in the meantime. Supabase's security advisor flags this
-- (rls_policy_always_true) — expected, and tracked, not an oversight.
alter table public.sessions enable row level security;
alter table public.messages enable row level security;
alter table public.evaluations enable row level security;

create policy "anon_full_access_pre_auth" on public.sessions
  for all to anon using (true) with check (true);

create policy "anon_full_access_pre_auth" on public.messages
  for all to anon using (true) with check (true);

create policy "anon_full_access_pre_auth" on public.evaluations
  for all to anon using (true) with check (true);
