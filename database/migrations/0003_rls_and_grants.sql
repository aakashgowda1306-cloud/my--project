-- =====================================================================
-- 0003 — Row Level Security (RLS) and privileges.
--
-- Two layers:
--   1. GRANTs decide which *tables/columns/actions* a role may touch at all.
--   2. RLS POLICIES decide which *rows* inside those tables it may touch.
-- With RLS enabled and no matching policy, the answer is always "no rows".
--
-- Pattern note: `(select auth.uid())` is used instead of `auth.uid()` so
-- Postgres evaluates it once per query instead of once per row.
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. Start from zero: remove the broad default grants, then add back.
-- ---------------------------------------------------------------------
revoke all on all tables    in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
revoke execute on all functions in schema public from public, anon, authenticated;

grant all on all tables    in schema public to service_role;
grant all on all sequences in schema public to service_role;
grant execute on all functions in schema public to service_role;

-- Public catalogue (landing page, course catalogue before sign-up)
grant select on public.courses, public.modules, public.achievements to anon;

-- Read-only learning content and lab data for signed-in learners
grant select on public.roles, public.courses, public.modules, public.lessons,
                public.exercises, public.quizzes, public.questions,
                public.lab_exercises, public.achievements,
                public.detection_rules, public.generated_alerts,
                public.course_progress
  to authenticated;

-- security_events: every column EXCEPT scenario_tag (the answer label)
grant select (id, event_time, source, host, username, src_ip, dst_ip, dst_port, protocol,
              event_code, category, action, outcome, severity, process_name, command_line,
              message, raw, dataset, is_synthetic)
  on public.security_events to authenticated;

-- Learner-owned data
grant select, update                 on public.profiles             to authenticated;
grant select, insert, update, delete on public.lesson_progress      to authenticated;
grant select, insert                 on public.study_sessions       to authenticated;
grant select, insert, update, delete on public.investigations       to authenticated;
grant select, insert, delete         on public.investigation_notes  to authenticated;
grant select, insert, update, delete on public.evidence_items       to authenticated;
grant select, insert                 on public.evidence_custody_events to authenticated;
grant select, insert, update, delete on public.incidents            to authenticated;
grant select, insert                 on public.incident_updates     to authenticated;
grant select, insert, update, delete on public.network_lab_sessions to authenticated;
-- Results are readable but only *written* by grading functions:
grant select on public.quiz_attempts, public.lab_submissions, public.user_achievements to authenticated;
-- Admin-only via RLS, but the role needs the privilege for the policy to matter:
grant select on public.audit_logs to authenticated;
-- Admin content management (RLS limits these to admins)
grant insert, update, delete on public.courses, public.modules, public.lessons, public.exercises,
                                public.quizzes, public.questions, public.lab_exercises,
                                public.achievements to authenticated;
grant update on public.detection_rules to authenticated;

grant usage on all sequences in schema public to authenticated;

-- Learners get their OWN streak only. current_streak(any_user) stays private;
-- this SECURITY DEFINER wrapper always passes the caller's id.
create or replace function public.my_streak()
returns integer language sql stable security definer set search_path = ''
as $$ select public.current_streak(auth.uid()); $$;
revoke execute on function public.my_streak() from public, anon;

-- Functions learners may call. Everything else (write_audit, current_streak,
-- evaluate_achievements, trigger functions) stays non-executable for them.
-- Note: trigger functions do not need EXECUTE for the user firing the trigger.
grant execute on function
  public.my_streak(), public.incident_stage_rank(text),
  public.submit_quiz_attempt(uuid, jsonb), public.submit_lab_answer(uuid, jsonb),
  public.transition_incident(uuid, text, text), public.ensure_lab_workspace()
  to authenticated;
-- is_admin() is used inside policies that anon can trigger (public catalogue).
grant execute on function public.is_admin() to anon, authenticated;

-- ---------------------------------------------------------------------
-- 2. Guard: only admins may change a role (blocks self-promotion).
-- ---------------------------------------------------------------------
create or replace function public.guard_profile_update()
returns trigger
language plpgsql set search_path = ''
as $$
begin
  if new.id <> old.id then
    raise exception 'profile id cannot change' using errcode = '42501';
  end if;
  if new.role_id is distinct from old.role_id
     and auth.role() = 'authenticated' and not public.is_admin() then
    raise exception 'only administrators can change roles' using errcode = '42501';
  end if;
  return new;
end;
$$;
revoke execute on function public.guard_profile_update() from public;

create trigger profiles_guard before update on public.profiles
  for each row execute function public.guard_profile_update();

-- ---------------------------------------------------------------------
-- 3. Enable RLS on every table.
-- ---------------------------------------------------------------------
do $$
declare t record;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t.tablename);
  end loop;
end $$;

-- ---------------------------------------------------------------------
-- 4. Policies
-- ---------------------------------------------------------------------
-- roles
create policy roles_read on public.roles for select to authenticated using (true);

-- profiles: see/edit yourself; admins see/edit everyone
create policy profiles_select on public.profiles for select to authenticated
  using (id = (select auth.uid()) or (select public.is_admin()));
create policy profiles_update on public.profiles for update to authenticated
  using (id = (select auth.uid()) or (select public.is_admin()))
  with check (id = (select auth.uid()) or (select public.is_admin()));

-- Published content is readable; admins manage everything
create policy courses_read on public.courses for select to anon, authenticated
  using (is_published or (select public.is_admin()));
create policy courses_admin on public.courses for all to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));

create policy modules_read on public.modules for select to anon, authenticated
  using (exists (select 1 from public.courses c where c.id = course_id
                 and (c.is_published or (select public.is_admin()))));
create policy modules_admin on public.modules for all to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));

create policy lessons_read on public.lessons for select to authenticated
  using (exists (select 1 from public.modules m join public.courses c on c.id = m.course_id
                 where m.id = module_id and (c.is_published or (select public.is_admin()))));
create policy lessons_admin on public.lessons for all to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));

create policy exercises_read on public.exercises for select to authenticated using (true);
create policy exercises_admin on public.exercises for all to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));
create policy quizzes_read on public.quizzes for select to authenticated using (true);
create policy quizzes_admin on public.quizzes for all to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));
create policy questions_read on public.questions for select to authenticated using (true);
create policy questions_admin on public.questions for all to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));
create policy lab_exercises_read on public.lab_exercises for select to authenticated using (true);
create policy lab_exercises_admin on public.lab_exercises for all to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));
create policy achievements_read on public.achievements for select to anon, authenticated using (true);
create policy achievements_admin on public.achievements for all to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));

-- Answer keys: RLS on, NO learner policies, NO grants → invisible to learners.

-- Progress: strictly your own rows
create policy lesson_progress_own on public.lesson_progress for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy study_sessions_own on public.study_sessions for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy quiz_attempts_own on public.quiz_attempts for select to authenticated
  using (user_id = (select auth.uid()) or (select public.is_admin()));
create policy lab_submissions_own on public.lab_submissions for select to authenticated
  using (user_id = (select auth.uid()) or (select public.is_admin()));
create policy user_achievements_own on public.user_achievements for select to authenticated
  using (user_id = (select auth.uid()) or (select public.is_admin()));

-- Shared synthetic SIEM data: read-only for learners
create policy security_events_read on public.security_events for select to authenticated using (true);
create policy detection_rules_read on public.detection_rules for select to authenticated using (true);
create policy detection_rules_admin on public.detection_rules for update to authenticated
  using ((select public.is_admin())) with check ((select public.is_admin()));
create policy generated_alerts_read on public.generated_alerts for select to authenticated using (true);

-- Investigations & notes: private to the learner
create policy investigations_own on public.investigations for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));
create policy investigation_notes_own on public.investigation_notes for all to authenticated
  using (user_id = (select auth.uid()))
  with check (
    user_id = (select auth.uid())
    and exists (select 1 from public.investigations i
                where i.id = investigation_id and i.user_id = (select auth.uid())));

-- Evidence: shared lab evidence (owner_id null) is readable; own evidence is editable
create policy evidence_read on public.evidence_items for select to authenticated
  using (owner_id is null or owner_id = (select auth.uid()));
create policy evidence_insert on public.evidence_items for insert to authenticated
  with check (owner_id = (select auth.uid()));
create policy evidence_modify on public.evidence_items for update to authenticated
  using (owner_id = (select auth.uid())) with check (owner_id = (select auth.uid()));
create policy evidence_delete on public.evidence_items for delete to authenticated
  using (owner_id = (select auth.uid()));

-- Chain of custody: append-only (no update/delete policies exist)
create policy custody_read on public.evidence_custody_events for select to authenticated
  using (exists (select 1 from public.evidence_items e where e.id = evidence_id
                 and (e.owner_id is null or e.owner_id = (select auth.uid()))));
create policy custody_insert on public.evidence_custody_events for insert to authenticated
  with check (recorded_by = (select auth.uid())
              and exists (select 1 from public.evidence_items e
                          where e.id = evidence_id and e.owner_id = (select auth.uid())));

-- Incidents: templates readable by all learners; own incidents fully managed
create policy incidents_read on public.incidents for select to authenticated
  using (is_template or owner_id = (select auth.uid()));
create policy incidents_insert on public.incidents for insert to authenticated
  with check (owner_id = (select auth.uid()) and not is_template);
create policy incidents_update on public.incidents for update to authenticated
  using (owner_id = (select auth.uid())) with check (owner_id = (select auth.uid()) and not is_template);
create policy incidents_delete on public.incidents for delete to authenticated
  using (owner_id = (select auth.uid()));

-- Incident history: learners may add comments only; stage history comes from the trigger
create policy incident_updates_read on public.incident_updates for select to authenticated
  using (exists (select 1 from public.incidents i where i.id = incident_id
                 and i.owner_id = (select auth.uid())));
create policy incident_updates_comment on public.incident_updates for insert to authenticated
  with check (user_id = (select auth.uid()) and from_stage is null and to_stage is null
              and exists (select 1 from public.incidents i where i.id = incident_id
                          and i.owner_id = (select auth.uid())));

-- Network lab sessions: private
create policy network_sessions_own on public.network_lab_sessions for all to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

-- Audit log: admins only
create policy audit_logs_admin on public.audit_logs for select to authenticated
  using ((select public.is_admin()));
