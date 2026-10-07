-- DateiSortieren – Datenbankschema für Supabase
-- Ausführen im Supabase-Dashboard unter "SQL Editor" (oder via `supabase db push`).
-- Jede Tabelle ist per Row Level Security (RLS) strikt pro Nutzer getrennt.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------- Profile
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  display_name text,
  avatar_url text,
  -- Einstellungen, die der Agent übernimmt (dry_run, ai_instructions, Vorlagen, …)
  settings jsonb not null default jsonb_build_object(
    'dry_run', true,
    'auto_apply_min_confidence', 0.85,
    'rename_template', '{date}_{vendor}_{doc_type}_{amount}',
    'organize_template', '{category}/{year}',
    'ai_instructions', '',
    'installer_max_age_days', 14,
    'media_enabled', false,
    'duplicates_enabled', true,
    'cleanup_enabled', true,
    'rename_enabled', true
  ),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Profil automatisch bei Registrierung anlegen (E-Mail und Google OAuth)
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email, display_name, avatar_url)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'full_name', new.raw_user_meta_data ->> 'name', split_part(new.email, '@', 1)),
    new.raw_user_meta_data ->> 'avatar_url'
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ------------------------------------------------------------- KI-Regeln
create table if not exists public.rules (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  name text not null,
  description text,
  priority int not null default 100,
  enabled boolean not null default true,
  -- {"extensions":[".pdf"],"name_contains":["telekom"],"content_keywords":["rechnung"],"category_is":"Finanzen"}
  match jsonb not null default '{}'::jsonb,
  action text not null default 'move' check (action in ('move', 'ignore', 'delete')),
  target text,            -- z. B. "Finanzen/Rechnungen/Telekom/{year}"
  rename_template text,   -- z. B. "{date}_Telekom_Rechnung_{amount}"
  tags text[] not null default '{}',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists rules_user_idx on public.rules (user_id, priority);

-- ------------------------------------------------------ Safe-List / Ausnahmen
create table if not exists public.safelist_entries (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  kind text not null check (kind in ('path', 'glob', 'extension', 'tag')),
  value text not null,
  note text,
  created_at timestamptz not null default now(),
  unique (user_id, kind, value)
);

-- ---------------------------------------------------------------- Agenten
create table if not exists public.agents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  name text not null,
  token_hash text not null unique,   -- SHA-256 des Tokens, das Token selbst wird nie gespeichert
  token_prefix text not null,        -- erste Zeichen zur Wiedererkennung
  hostname text,
  platform text,
  version text,
  info jsonb not null default '{}'::jsonb,
  last_seen_at timestamptz,
  scan_requested_at timestamptz,
  created_at timestamptz not null default now()
);
create index if not exists agents_user_idx on public.agents (user_id);

-- ------------------------------------------------- Aktionen (Manifest-Spiegel)
create table if not exists public.actions (
  id uuid primary key,
  user_id uuid not null references auth.users (id) on delete cascade,
  agent_id uuid references public.agents (id) on delete set null,
  batch_id uuid,
  kind text not null check (kind in ('move', 'delete', 'compress')),
  status text not null default 'proposed' check (status in
    ('proposed', 'approved', 'rejected', 'applied', 'skipped', 'failed', 'undo_requested', 'undone')),
  src_path text not null,
  dst_path text,
  reason text,
  confidence real,
  category text,
  tags text[] not null default '{}',
  details jsonb not null default '{}'::jsonb,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  applied_at timestamptz,
  undone_at timestamptz
);
create index if not exists actions_user_status_idx on public.actions (user_id, status, created_at desc);
create index if not exists actions_agent_status_idx on public.actions (agent_id, status);
create index if not exists actions_batch_idx on public.actions (batch_id);

-- ------------------------------------------------------- Aktivitäts-Logs
create table if not exists public.activity_logs (
  id bigint generated always as identity primary key,
  user_id uuid not null default auth.uid() references auth.users (id) on delete cascade,
  agent_id uuid references public.agents (id) on delete set null,
  level text not null default 'info' check (level in ('debug', 'info', 'warning', 'error')),
  message text not null,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists activity_logs_user_idx on public.activity_logs (user_id, created_at desc);

-- --------------------------------------------------------- updated_at
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_touch on public.profiles;
create trigger profiles_touch before update on public.profiles for each row execute function public.touch_updated_at();
drop trigger if exists rules_touch on public.rules;
create trigger rules_touch before update on public.rules for each row execute function public.touch_updated_at();
drop trigger if exists actions_touch on public.actions;
create trigger actions_touch before update on public.actions for each row execute function public.touch_updated_at();

-- ------------------------------------------------- Row Level Security
alter table public.profiles enable row level security;
alter table public.rules enable row level security;
alter table public.safelist_entries enable row level security;
alter table public.agents enable row level security;
alter table public.actions enable row level security;
alter table public.activity_logs enable row level security;

drop policy if exists "own profile" on public.profiles;
create policy "own profile" on public.profiles
  for all using (auth.uid() = id) with check (auth.uid() = id);

drop policy if exists "own rules" on public.rules;
create policy "own rules" on public.rules
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own safelist" on public.safelist_entries;
create policy "own safelist" on public.safelist_entries
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

drop policy if exists "own agents" on public.agents;
create policy "own agents" on public.agents
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- Nutzer dürfen Aktionen lesen und den Status ändern (Freigeben / Ablehnen / Undo anfordern).
-- Anlegen tut ausschließlich der Agent über die API (Service-Role).
drop policy if exists "read own actions" on public.actions;
create policy "read own actions" on public.actions
  for select using (auth.uid() = user_id);
drop policy if exists "update own actions" on public.actions;
create policy "update own actions" on public.actions
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "delete own actions" on public.actions;
create policy "delete own actions" on public.actions
  for delete using (auth.uid() = user_id);

drop policy if exists "read own logs" on public.activity_logs;
create policy "read own logs" on public.activity_logs
  for select using (auth.uid() = user_id);
drop policy if exists "write own logs" on public.activity_logs;
create policy "write own logs" on public.activity_logs
  for insert with check (auth.uid() = user_id);

-- Nur erlaubte Statuswechsel aus dem Dashboard (Agent nutzt Service-Role und ist ausgenommen)
create or replace function public.guard_action_status()
returns trigger language plpgsql as $$
begin
  if auth.role() = 'authenticated' and new.status is distinct from old.status then
    if not (
      (old.status in ('proposed', 'failed') and new.status in ('approved', 'rejected')) or
      (old.status = 'approved' and new.status in ('proposed', 'rejected')) or
      (old.status = 'rejected' and new.status = 'proposed') or
      (old.status = 'applied' and new.status = 'undo_requested') or
      (old.status = 'undo_requested' and new.status = 'applied')
    ) then
      raise exception 'Statuswechsel % -> % ist nicht erlaubt', old.status, new.status;
    end if;
  end if;
  if auth.role() = 'authenticated' then
    -- Pfade und Inhalte darf nur der Agent verändern
    new.src_path = old.src_path;
    new.dst_path = old.dst_path;
    new.kind = old.kind;
    new.user_id = old.user_id;
    new.agent_id = old.agent_id;
  end if;
  return new;
end;
$$;

drop trigger if exists actions_guard on public.actions;
create trigger actions_guard before update on public.actions for each row execute function public.guard_action_status();

-- ------------------------------------------------------ Live-Updates
do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    begin
      alter publication supabase_realtime add table public.actions;
    exception when duplicate_object then null;
    end;
    begin
      alter publication supabase_realtime add table public.activity_logs;
    exception when duplicate_object then null;
    end;
  end if;
end $$;
