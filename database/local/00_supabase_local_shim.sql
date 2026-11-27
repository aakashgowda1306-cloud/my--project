-- =====================================================================
-- LOCAL DEVELOPMENT ONLY — DO NOT RUN ON SUPABASE.
--
-- Supabase already provides everything in this file (the auth schema,
-- auth.users, auth.uid(), and the anon/authenticated/service_role roles).
-- This shim recreates the minimum of it on a plain PostgreSQL server so the
-- real migrations in ../migrations run unchanged and RLS can be tested.
--
-- auth.uid() is implemented the same way Supabase implements it: it reads
-- the "sub" claim from the request.jwt.claims setting for the current
-- transaction. Note the nullif(..., ''): after a transaction ends, Postgres
-- resets a custom setting to an EMPTY STRING (not NULL), and ''::jsonb fails.
-- =====================================================================

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then
    create role authenticated nologin noinherit;
  end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then
    create role service_role nologin noinherit bypassrls;
  end if;
end $$;

-- Let the connecting (owner) user switch into these roles with SET ROLE.
grant anon, authenticated, service_role to current_user;

create schema if not exists auth;
grant usage on schema auth to anon, authenticated, service_role;

create table if not exists auth.users (
  id                 uuid primary key default gen_random_uuid(),
  email              text unique not null,
  encrypted_password text,
  raw_user_meta_data jsonb not null default '{}'::jsonb,
  created_at         timestamptz not null default now()
);

create or replace function auth.uid() returns uuid
language sql stable as $$
  select nullif(
    coalesce(
      nullif(current_setting('request.jwt.claim.sub', true), ''),
      nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub'
    ), ''
  )::uuid
$$;

create or replace function auth.role() returns text
language sql stable as $$
  select coalesce(
    nullif(current_setting('request.jwt.claim.role', true), ''),
    nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'role'
  )
$$;

create or replace function auth.jwt() returns jsonb
language sql stable as $$
  select coalesce(nullif(current_setting('request.jwt.claims', true), ''), '{}')::jsonb
$$;

grant execute on function auth.uid(), auth.role(), auth.jwt()
  to anon, authenticated, service_role;

-- Supabase grants these roles usage on the public schema.
grant usage on schema public to anon, authenticated, service_role;
