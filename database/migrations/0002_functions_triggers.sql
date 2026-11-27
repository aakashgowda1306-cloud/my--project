-- =====================================================================
-- 0002 — Functions and triggers.
--
-- SECURITY DEFINER functions run with the privileges of their owner, so
-- they can read hidden tables (answer keys) or write protected tables
-- (scores, achievements, audit log). Every one of them:
--   * sets search_path = '' (prevents search-path hijacking), and
--   * checks auth.uid() itself, because RLS does not protect it.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Helpers
-- ---------------------------------------------------------------------
create or replace function public.is_admin()
returns boolean
language sql stable security definer set search_path = ''
as $$
  select exists (
    select 1 from public.profiles p
    join public.roles r on r.id = p.role_id
    where p.id = auth.uid() and r.name = 'admin'
  );
$$;

create or replace function public.set_updated_at()
returns trigger language plpgsql set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

create trigger profiles_updated_at       before update on public.profiles
  for each row execute function public.set_updated_at();
create trigger lesson_progress_updated_at before update on public.lesson_progress
  for each row execute function public.set_updated_at();
create trigger investigations_updated_at before update on public.investigations
  for each row execute function public.set_updated_at();
create trigger incidents_updated_at      before update on public.incidents
  for each row execute function public.set_updated_at();

create or replace function public.write_audit(
  p_actor uuid, p_action text, p_entity_type text, p_entity_id text, p_metadata jsonb default '{}'::jsonb)
returns void
language sql security definer set search_path = ''
as $$
  insert into public.audit_logs (actor_id, action, entity_type, entity_id, metadata)
  values (p_actor, p_action, p_entity_type, p_entity_id, coalesce(p_metadata, '{}'::jsonb));
$$;

-- ---------------------------------------------------------------------
-- New user → profile (standard Supabase pattern)
-- ---------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql security definer set search_path = ''
as $$
declare
  v_name text;
begin
  v_name := coalesce(
    nullif(trim(new.raw_user_meta_data ->> 'display_name'), ''),
    split_part(new.email, '@', 1));
  if char_length(v_name) < 2 then
    v_name := 'Learner';
  end if;
  insert into public.profiles (id, display_name)
  values (new.id, left(v_name, 60));
  perform public.write_audit(new.id, 'user.registered', 'profile', new.id::text, '{}'::jsonb);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Role changes are audited (only admins can perform them; see 0003).
create or replace function public.audit_role_change()
returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
  if new.role_id is distinct from old.role_id then
    perform public.write_audit(auth.uid(), 'profile.role_changed', 'profile', new.id::text,
      jsonb_build_object('from', old.role_id, 'to', new.role_id));
  end if;
  return new;
end;
$$;

create trigger profiles_audit_role after update of role_id on public.profiles
  for each row execute function public.audit_role_change();

-- ---------------------------------------------------------------------
-- Learning streak (consecutive days with any learning activity)
-- ---------------------------------------------------------------------
create or replace function public.current_streak(p_user uuid)
returns integer
language sql stable security definer set search_path = ''
as $$
  with days as (
    select distinct (ts at time zone 'UTC')::date as d from (
      select completed_at as ts from public.lesson_progress where user_id = p_user and completed_at is not null
      union all select created_at from public.quiz_attempts  where user_id = p_user
      union all select created_at from public.lab_submissions where user_id = p_user
      union all select started_at from public.study_sessions  where user_id = p_user
    ) a
  ),
  islands as (
    select d, d - (row_number() over (order by d))::int as grp from days
  ),
  runs as (
    select max(d) as last_day, count(*)::int as len from islands group by grp
  )
  select coalesce((
    select len from runs
    where last_day >= ((now() at time zone 'UTC')::date - 1)
    order by last_day desc limit 1), 0);
$$;

-- ---------------------------------------------------------------------
-- Achievements: awarded only by this function, never by clients
-- ---------------------------------------------------------------------
create or replace function public.evaluate_achievements(p_user uuid)
returns integer
language plpgsql security definer set search_path = ''
as $$
declare
  a record;
  v_value integer;
  v_awarded integer := 0;
begin
  if p_user is null then
    return 0;
  end if;
  if auth.uid() is not null and auth.uid() <> p_user and not public.is_admin() then
    raise exception 'not allowed' using errcode = '42501';
  end if;

  for a in
    select ach.* from public.achievements ach
    where not exists (select 1 from public.user_achievements ua
                      where ua.user_id = p_user and ua.achievement_id = ach.id)
  loop
    v_value := case a.criteria ->> 'metric'
      when 'lessons_completed' then
        (select count(*) from public.lesson_progress where user_id = p_user and status = 'completed')
      when 'quizzes_passed' then
        (select count(distinct quiz_id) from public.quiz_attempts where user_id = p_user and passed)
      when 'perfect_quizzes' then
        (select count(distinct quiz_id) from public.quiz_attempts where user_id = p_user and score_pct = 100)
      when 'labs_solved' then
        (select count(distinct lab_exercise_id) from public.lab_submissions where user_id = p_user and is_correct)
      when 'investigations_closed' then
        (select count(*) from public.investigations where user_id = p_user and status like 'closed_%')
      when 'incidents_resolved' then
        (select count(*) from public.incidents where owner_id = p_user and stage = 'lessons_learned')
      when 'streak_days' then public.current_streak(p_user)
      else 0
    end;

    if v_value >= (a.criteria ->> 'threshold')::int then
      insert into public.user_achievements (user_id, achievement_id)
      values (p_user, a.id) on conflict do nothing;
      v_awarded := v_awarded + 1;
    end if;
  end loop;
  return v_awarded;
end;
$$;

create or replace function public.trg_evaluate_achievements()
returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
  -- NEW has different columns per table, so branch instead of using one expression.
  if tg_table_name = 'incidents' then
    perform public.evaluate_achievements(new.owner_id);
  else
    perform public.evaluate_achievements(new.user_id);
  end if;
  return null;
end;
$$;

create trigger lesson_progress_achievements after insert or update on public.lesson_progress
  for each row execute function public.trg_evaluate_achievements();
create trigger investigations_achievements after update of status on public.investigations
  for each row execute function public.trg_evaluate_achievements();
create trigger incidents_achievements after update of stage on public.incidents
  for each row when (new.owner_id is not null)
  execute function public.trg_evaluate_achievements();

-- ---------------------------------------------------------------------
-- Quiz grading (server-side; learners never see answer keys beforehand)
-- p_answers format: {"<question_id>": <selected option index>, ...}
-- ---------------------------------------------------------------------
create or replace function public.submit_quiz_attempt(p_quiz_id uuid, p_answers jsonb)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare
  v_user uuid := auth.uid();
  v_total integer;
  v_correct integer;
  v_pass_mark integer;
  v_score numeric(5, 2);
  v_attempt_id uuid;
  v_results jsonb;
begin
  if v_user is null then
    raise exception 'authentication required' using errcode = '42501';
  end if;
  if p_answers is null or jsonb_typeof(p_answers) <> 'object' then
    raise exception 'answers must be a JSON object' using errcode = '22023';
  end if;

  select pass_mark into v_pass_mark from public.quizzes where id = p_quiz_id;
  if not found then
    raise exception 'quiz not found' using errcode = 'P0002';
  end if;

  select
    count(*),
    count(*) filter (where (p_answers ->> q.id::text) ~ '^[0-9]+$'
                       and (p_answers ->> q.id::text)::int = k.correct_option),
    jsonb_agg(jsonb_build_object(
      'question_id', q.id,
      'selected', p_answers -> q.id::text,
      'correct_option', k.correct_option,
      'is_correct', coalesce((p_answers ->> q.id::text) ~ '^[0-9]+$'
                       and (p_answers ->> q.id::text)::int = k.correct_option, false),
      'explanation', k.explanation) order by q.order_index)
  into v_total, v_correct, v_results
  from public.questions q
  join public.question_answer_keys k on k.question_id = q.id
  where q.quiz_id = p_quiz_id;

  if v_total = 0 then
    raise exception 'quiz has no questions' using errcode = 'P0002';
  end if;

  v_score := round(100.0 * v_correct / v_total, 2);

  insert into public.quiz_attempts (user_id, quiz_id, answers, correct_count, total_count, score_pct, passed)
  values (v_user, p_quiz_id, p_answers, v_correct, v_total, v_score, v_score >= v_pass_mark)
  returning id into v_attempt_id;

  insert into public.study_sessions (user_id, activity, ref_id) values (v_user, 'quiz', p_quiz_id);
  perform public.write_audit(v_user, 'quiz.submitted', 'quiz', p_quiz_id::text,
    jsonb_build_object('score_pct', v_score));
  perform public.evaluate_achievements(v_user);

  return jsonb_build_object(
    'attempt_id', v_attempt_id, 'correct_count', v_correct, 'total_count', v_total,
    'score_pct', v_score, 'pass_mark', v_pass_mark, 'passed', v_score >= v_pass_mark,
    'results', v_results);
end;
$$;

-- ---------------------------------------------------------------------
-- Lab grading. Answer key format: {"field": "expected value", ...}
-- Comparison is case-insensitive and ignores surrounding whitespace.
-- ---------------------------------------------------------------------
create or replace function public.submit_lab_answer(p_lab_exercise_id uuid, p_answers jsonb)
returns jsonb
language plpgsql security definer set search_path = ''
as $$
declare
  v_user uuid := auth.uid();
  v_expected jsonb;
  v_explanation text;
  v_max integer;
  v_total integer;
  v_matched integer;
  v_score integer;
  v_feedback jsonb;
  v_id uuid;
begin
  if v_user is null then
    raise exception 'authentication required' using errcode = '42501';
  end if;
  if p_answers is null or jsonb_typeof(p_answers) <> 'object' then
    raise exception 'answers must be a JSON object' using errcode = '22023';
  end if;

  select k.expected, k.explanation, e.max_score
    into v_expected, v_explanation, v_max
  from public.lab_exercises e
  join public.lab_exercise_answer_keys k on k.lab_exercise_id = e.id
  where e.id = p_lab_exercise_id;
  if not found then
    raise exception 'lab exercise not found' using errcode = 'P0002';
  end if;

  select count(*),
         count(*) filter (where lower(trim(coalesce(p_answers ->> key, ''))) = lower(trim(value))),
         jsonb_agg(jsonb_build_object(
           'field', key,
           'is_correct', lower(trim(coalesce(p_answers ->> key, ''))) = lower(trim(value))) order by key)
    into v_total, v_matched, v_feedback
  from jsonb_each_text(v_expected);

  v_score := (v_max * v_matched) / greatest(v_total, 1);

  insert into public.lab_submissions (user_id, lab_exercise_id, answers, score, max_score, is_correct, feedback)
  values (v_user, p_lab_exercise_id, p_answers, v_score, v_max, v_matched = v_total, v_feedback)
  returning id into v_id;

  insert into public.study_sessions (user_id, activity, ref_id) values (v_user, 'lab', p_lab_exercise_id);
  perform public.write_audit(v_user, 'lab.submitted', 'lab_exercise', p_lab_exercise_id::text,
    jsonb_build_object('score', v_score, 'max_score', v_max));
  perform public.evaluate_achievements(v_user);

  return jsonb_build_object(
    'submission_id', v_id, 'score', v_score, 'max_score', v_max,
    'is_correct', v_matched = v_total, 'feedback', v_feedback,
    -- Explanation is only revealed once the learner gets it fully right.
    'explanation', case when v_matched = v_total then v_explanation end);
end;
$$;

-- ---------------------------------------------------------------------
-- Incident workflow: stages move forward one step at a time (or back one
-- step for rework). Key stages require their documentation first.
-- ---------------------------------------------------------------------
create or replace function public.incident_stage_rank(p_stage text)
returns integer language sql immutable set search_path = ''
as $$
  select array_position(array[
    'alert_received', 'triage', 'investigation', 'evidence_collection', 'impact_assessment',
    'containment_planning', 'recovery_planning', 'resolution', 'lessons_learned'], p_stage);
$$;

create or replace function public.enforce_incident_transition()
returns trigger
language plpgsql set search_path = ''
as $$
declare
  v_diff integer;
begin
  if new.stage is not distinct from old.stage then
    return new;
  end if;
  if old.is_template then
    raise exception 'template incidents are read-only' using errcode = '42501';
  end if;

  v_diff := public.incident_stage_rank(new.stage) - public.incident_stage_rank(old.stage);
  if v_diff not in (1, -1) then
    raise exception 'invalid incident transition % -> % (move one stage at a time)',
      old.stage, new.stage using errcode = '22023';
  end if;

  if v_diff = 1 then
    if new.stage = 'containment_planning' and coalesce(trim(new.impact_assessment), '') = '' then
      raise exception 'record an impact assessment before containment planning' using errcode = '22023';
    elsif new.stage = 'recovery_planning' and coalesce(trim(new.containment_plan), '') = '' then
      raise exception 'record a containment plan before recovery planning' using errcode = '22023';
    elsif new.stage = 'resolution' and coalesce(trim(new.recovery_plan), '') = '' then
      raise exception 'record a recovery plan before resolution' using errcode = '22023';
    elsif new.stage = 'lessons_learned' and coalesce(trim(new.resolution_summary), '') = '' then
      raise exception 'record a resolution summary before lessons learned' using errcode = '22023';
    end if;
  end if;

  new.resolved_at := case when new.stage in ('resolution', 'lessons_learned')
                          then coalesce(old.resolved_at, now()) end;
  return new;
end;
$$;

create trigger incidents_enforce_transition before update of stage on public.incidents
  for each row execute function public.enforce_incident_transition();

create or replace function public.record_incident_transition()
returns trigger
language plpgsql security definer set search_path = ''
as $$
begin
  if new.stage is distinct from old.stage then
    insert into public.incident_updates (incident_id, user_id, from_stage, to_stage, note)
    values (new.id, auth.uid(), old.stage, new.stage,
            nullif(current_setting('app.transition_note', true), ''));
    perform public.write_audit(auth.uid(), 'incident.stage_changed', 'incident', new.id::text,
      jsonb_build_object('from', old.stage, 'to', new.stage));
  end if;
  return null;
end;
$$;

create trigger incidents_record_transition after update of stage on public.incidents
  for each row execute function public.record_incident_transition();

-- Convenience wrapper used by the API: SECURITY INVOKER, so RLS still decides
-- whether the caller may update the incident at all.
create or replace function public.transition_incident(p_incident_id uuid, p_to_stage text, p_note text default null)
returns public.incidents
language plpgsql set search_path = ''
as $$
declare
  v_row public.incidents;
begin
  perform set_config('app.transition_note', coalesce(p_note, ''), true);
  update public.incidents set stage = p_to_stage where id = p_incident_id
  returning * into v_row;
  if not found then
    raise exception 'incident not found' using errcode = 'P0002';
  end if;
  perform set_config('app.transition_note', '', true);
  return v_row;
end;
$$;

-- ---------------------------------------------------------------------
-- Lab workspace: copy the fictional template incidents for a new learner
-- ---------------------------------------------------------------------
create or replace function public.ensure_lab_workspace()
returns integer
language plpgsql security definer set search_path = ''
as $$
declare
  v_user uuid := auth.uid();
  v_count integer;
begin
  if v_user is null then
    raise exception 'authentication required' using errcode = '42501';
  end if;

  insert into public.incidents (
    owner_id, is_template, template_id, reference, title, category, severity, stage,
    assigned_analyst, summary, related_alert_id, detected_at)
  select v_user, false, t.id, t.reference, t.title, t.category, t.severity, 'alert_received',
         t.assigned_analyst, t.summary, t.related_alert_id, t.detected_at
  from public.incidents t
  where t.is_template
  on conflict (owner_id, template_id) do nothing;

  get diagnostics v_count = row_count;
  return v_count;
end;
$$;

-- ---------------------------------------------------------------------
-- Progress view (security_invoker → RLS of the caller applies)
-- ---------------------------------------------------------------------
create view public.course_progress with (security_invoker = true) as
select
  c.id   as course_id,
  c.slug as course_slug,
  count(l.id)::int as total_lessons,
  count(lp.lesson_id) filter (where lp.status = 'completed')::int as completed_lessons,
  case when count(l.id) = 0 then 0
       else round(100.0 * count(lp.lesson_id) filter (where lp.status = 'completed') / count(l.id), 1)
  end as percent_complete
from public.courses c
join public.modules m on m.course_id = c.id
join public.lessons l on l.module_id = m.id
left join public.lesson_progress lp on lp.lesson_id = l.id and lp.user_id = auth.uid()
where c.is_published
group by c.id, c.slug;
