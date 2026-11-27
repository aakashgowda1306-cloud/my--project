-- =====================================================================
-- 0001 — Core schema: tables, keys, constraints, indexes.
-- Runs unchanged on Supabase (SQL editor / CLI) and on local Postgres
-- (after database/local/00_supabase_local_shim.sql).
-- Security (RLS + grants) is in 0003. Functions/triggers are in 0002.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Identity & roles
-- ---------------------------------------------------------------------
create table public.roles (
  id   smallint primary key,
  name text not null unique check (name in ('student', 'instructor', 'admin'))
);

insert into public.roles (id, name) values
  (1, 'student'), (2, 'instructor'), (3, 'admin');

create table public.profiles (
  id                   uuid primary key references auth.users (id) on delete cascade,
  display_name         text not null check (char_length(display_name) between 2 and 60),
  role_id              smallint not null default 1 references public.roles (id),
  experience_level     text not null default 'beginner'
                       check (experience_level in ('beginner', 'intermediate', 'advanced')),
  learning_goal        text check (char_length(learning_goal) <= 280),
  onboarding_completed boolean not null default false,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now()
);
create index profiles_role_idx on public.profiles (role_id);

-- ---------------------------------------------------------------------
-- Academy: courses → modules → lessons → exercises / quizzes
-- ---------------------------------------------------------------------
create table public.courses (
  id            uuid primary key default gen_random_uuid(),
  slug          text not null unique check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  title         text not null check (char_length(title) between 3 and 120),
  summary       text not null,
  learning_path text not null,
  level         text not null check (level in ('beginner', 'intermediate', 'advanced')),
  department    text not null check (department in
                  ('academy', 'soc', 'siem', 'forensics', 'network', 'incident_response')),
  order_index   integer not null check (order_index >= 0),
  is_published  boolean not null default false,
  created_at    timestamptz not null default now()
);

create table public.modules (
  id          uuid primary key default gen_random_uuid(),
  course_id   uuid not null references public.courses (id) on delete cascade,
  slug        text not null check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  title       text not null,
  summary     text,
  order_index integer not null check (order_index >= 0),
  unique (course_id, slug),
  unique (course_id, order_index)
);
create index modules_course_idx on public.modules (course_id);

create table public.lessons (
  id                uuid primary key default gen_random_uuid(),
  module_id         uuid not null references public.modules (id) on delete cascade,
  slug              text not null check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  title             text not null,
  summary           text not null,
  content_md        text not null,
  learning_outcome  text not null,
  estimated_minutes integer not null check (estimated_minutes between 1 and 240),
  video_storyboard  jsonb,
  order_index       integer not null check (order_index >= 0),
  unique (module_id, slug),
  unique (module_id, order_index)
);
create index lessons_module_idx on public.lessons (module_id);

-- Lab exercises (shared by the Academy and the department labs)
create table public.lab_exercises (
  id                     uuid primary key default gen_random_uuid(),
  slug                   text not null unique,
  department             text not null check (department in
                           ('soc', 'siem', 'forensics', 'network', 'incident_response')),
  title                  text not null,
  difficulty             text not null check (difficulty in ('beginner', 'intermediate', 'advanced')),
  objective              text not null,       -- educational objective
  authorised_environment text not null,       -- where it is allowed to run
  expected_result        text not null,
  safety_restrictions    text not null,
  instructions_md        text not null,
  answer_fields          jsonb not null default '[]'::jsonb
                         check (jsonb_typeof(answer_fields) = 'array'),
  max_score              integer not null default 100 check (max_score > 0),
  created_at             timestamptz not null default now()
);

-- Hidden from learners (no RLS policy grants access). Used only by grading functions.
create table public.lab_exercise_answer_keys (
  lab_exercise_id uuid primary key references public.lab_exercises (id) on delete cascade,
  expected        jsonb not null check (jsonb_typeof(expected) = 'object'),
  explanation     text not null
);

create table public.exercises (
  id                     uuid primary key default gen_random_uuid(),
  lesson_id              uuid not null references public.lessons (id) on delete cascade,
  lab_exercise_id        uuid references public.lab_exercises (id) on delete set null,
  title                  text not null,
  objective              text not null,
  authorised_environment text not null,
  expected_result        text not null,
  safety_restrictions    text not null,
  instructions_md        text not null,
  order_index            integer not null default 0,
  unique (lesson_id, order_index)
);
create index exercises_lesson_idx on public.exercises (lesson_id);

create table public.quizzes (
  id        uuid primary key default gen_random_uuid(),
  lesson_id uuid unique references public.lessons (id) on delete cascade,
  title     text not null,
  pass_mark integer not null default 70 check (pass_mark between 1 and 100)
);

create table public.questions (
  id          uuid primary key default gen_random_uuid(),
  quiz_id     uuid not null references public.quizzes (id) on delete cascade,
  order_index integer not null check (order_index >= 0),
  prompt      text not null,
  options     jsonb not null check (
                jsonb_typeof(options) = 'array'
                and jsonb_array_length(options) between 2 and 6),
  unique (quiz_id, order_index)
);
create index questions_quiz_idx on public.questions (quiz_id);

-- Hidden from learners. Used only by submit_quiz_attempt().
create table public.question_answer_keys (
  question_id    uuid primary key references public.questions (id) on delete cascade,
  correct_option integer not null check (correct_option >= 0),
  explanation    text not null
);

-- ---------------------------------------------------------------------
-- Learner progress
-- ---------------------------------------------------------------------
create table public.lesson_progress (
  user_id      uuid not null references public.profiles (id) on delete cascade,
  lesson_id    uuid not null references public.lessons (id) on delete cascade,
  status       text not null default 'in_progress'
               check (status in ('in_progress', 'completed')),
  started_at   timestamptz not null default now(),
  completed_at timestamptz,
  updated_at   timestamptz not null default now(),
  primary key (user_id, lesson_id),
  check ((status = 'completed') = (completed_at is not null))
);
create index lesson_progress_lesson_idx on public.lesson_progress (lesson_id);

create table public.quiz_attempts (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references public.profiles (id) on delete cascade,
  quiz_id       uuid not null references public.quizzes (id) on delete cascade,
  answers       jsonb not null check (jsonb_typeof(answers) = 'object'),
  correct_count integer not null check (correct_count >= 0),
  total_count   integer not null check (total_count > 0),
  score_pct     numeric(5, 2) not null check (score_pct between 0 and 100),
  passed        boolean not null,
  created_at    timestamptz not null default now(),
  check (correct_count <= total_count)
);
create index quiz_attempts_user_idx on public.quiz_attempts (user_id, created_at desc);
create index quiz_attempts_quiz_idx on public.quiz_attempts (quiz_id);

create table public.achievements (
  id          uuid primary key default gen_random_uuid(),
  code        text not null unique,
  title       text not null,
  description text not null,
  icon        text not null,
  criteria    jsonb not null check (criteria ? 'metric' and criteria ? 'threshold')
);

create table public.user_achievements (
  user_id        uuid not null references public.profiles (id) on delete cascade,
  achievement_id uuid not null references public.achievements (id) on delete cascade,
  awarded_at     timestamptz not null default now(),
  primary key (user_id, achievement_id)
);

create table public.study_sessions (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.profiles (id) on delete cascade,
  activity   text not null check (activity in ('lesson', 'quiz', 'lab', 'investigation', 'incident')),
  ref_id     uuid,
  started_at timestamptz not null default now(),
  minutes    integer not null default 0 check (minutes between 0 and 600)
);
create index study_sessions_user_idx on public.study_sessions (user_id, started_at desc);

-- ---------------------------------------------------------------------
-- SIEM: synthetic events, detection rules, generated alerts
-- ---------------------------------------------------------------------
create table public.security_events (
  id           bigint primary key,
  event_time   timestamptz not null,
  source       text not null check (source in
                 ('windows', 'linux', 'application', 'authentication', 'network')),
  host         text not null,
  username     text,
  src_ip       inet,
  dst_ip       inet,
  dst_port     integer check (dst_port between 0 and 65535),
  protocol     text,
  event_code   text not null,
  category     text not null,
  action       text not null,
  outcome      text not null check (outcome in ('success', 'failure', 'unknown')),
  severity     text not null check (severity in ('info', 'low', 'medium', 'high', 'critical')),
  process_name text,
  command_line text,
  message      text not null,
  raw          jsonb not null default '{}'::jsonb,
  scenario_tag text,            -- internal answer label; NOT granted to learners
  dataset      text not null default 'synthetic-v1',
  is_synthetic boolean not null default true check (is_synthetic)
);
create index security_events_time_idx     on public.security_events (event_time desc);
create index security_events_severity_idx on public.security_events (severity, event_time desc);
create index security_events_source_idx   on public.security_events (source, event_time desc);
create index security_events_host_idx     on public.security_events (host);
create index security_events_user_idx     on public.security_events (username);
create index security_events_code_idx     on public.security_events (event_code);

create table public.detection_rules (
  id                   text primary key check (id ~ '^CSA-DET-[0-9]{3}$'),
  name                 text not null,
  severity             text not null check (severity in ('low', 'medium', 'high', 'critical')),
  mitre_technique_id   text check (mitre_technique_id ~ '^T[0-9]{4}(\.[0-9]{3})?$'),
  mitre_technique_name text,
  mitre_tactic         text,
  data_sources         text[] not null,
  what_detected        text not null,
  why_it_matters       text not null,
  evidence_guidance    text not null,
  analyst_steps        text not null,
  defensive_response   text not null,
  parameters           jsonb not null default '{}'::jsonb,
  enabled              boolean not null default true
);

create table public.generated_alerts (
  id                 bigint generated always as identity primary key,
  rule_id            text not null references public.detection_rules (id) on delete cascade,
  alert_key          text not null unique,      -- makes re-running detections idempotent
  title              text not null,
  severity           text not null check (severity in ('low', 'medium', 'high', 'critical')),
  entity             jsonb not null default '{}'::jsonb,
  first_seen         timestamptz not null,
  last_seen          timestamptz not null,
  event_count        integer not null check (event_count > 0),
  evidence_event_ids bigint[] not null,
  summary            text not null,
  created_at         timestamptz not null default now(),
  check (last_seen >= first_seen)
);
create index generated_alerts_rule_idx     on public.generated_alerts (rule_id);
create index generated_alerts_severity_idx on public.generated_alerts (severity, first_seen desc);

-- ---------------------------------------------------------------------
-- Investigations (alert triage + forensic cases), private per learner
-- ---------------------------------------------------------------------
create table public.investigations (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.profiles (id) on delete cascade,
  kind       text not null check (kind in ('alert_triage', 'forensic_case')),
  alert_id   bigint references public.generated_alerts (id) on delete cascade,
  case_ref   text,
  title      text not null check (char_length(title) between 3 and 160),
  status     text not null default 'new' check (status in
               ('new', 'in_progress', 'escalated',
                'closed_true_positive', 'closed_false_positive', 'closed_benign')),
  summary    text check (char_length(summary) <= 5000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check ((kind = 'alert_triage') = (alert_id is not null)),
  unique (user_id, alert_id)
);
create index investigations_user_idx on public.investigations (user_id, updated_at desc);
create index investigations_alert_idx on public.investigations (alert_id);

-- ---------------------------------------------------------------------
-- Digital forensics evidence + append-only chain of custody
-- ---------------------------------------------------------------------
create table public.evidence_items (
  id            uuid primary key default gen_random_uuid(),
  owner_id      uuid references public.profiles (id) on delete cascade, -- null = shared lab evidence
  case_ref      text not null,
  label         text not null,
  evidence_type text not null check (evidence_type in
                  ('log_file', 'disk_image', 'memory_capture', 'email', 'document',
                   'configuration', 'browser_artifact', 'network_capture', 'other')),
  description   text not null,
  file_name     text not null,
  size_bytes    bigint not null check (size_bytes >= 0),
  sha256        text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  md5           text check (md5 ~ '^[0-9a-f]{32}$'),
  source_host   text,
  acquired_at   timestamptz not null,
  acquired_by   text not null,
  storage_path  text,
  metadata      jsonb not null default '{}'::jsonb,
  is_synthetic  boolean not null default true check (is_synthetic),
  created_at    timestamptz not null default now()
);
create index evidence_items_owner_idx on public.evidence_items (owner_id);
create index evidence_items_case_idx  on public.evidence_items (case_ref);

create table public.evidence_custody_events (
  id          bigint generated always as identity primary key,
  evidence_id uuid not null references public.evidence_items (id) on delete cascade,
  action      text not null check (action in
                ('collected', 'hashed', 'transferred', 'analysed', 'stored', 'hash_verified', 'released')),
  actor       text not null,
  location    text not null,
  notes       text,
  occurred_at timestamptz not null,
  recorded_by uuid references public.profiles (id) on delete set null,
  created_at  timestamptz not null default now()
);
create index custody_evidence_idx on public.evidence_custody_events (evidence_id, occurred_at);

create table public.investigation_notes (
  id               uuid primary key default gen_random_uuid(),
  investigation_id uuid not null references public.investigations (id) on delete cascade,
  user_id          uuid not null references public.profiles (id) on delete cascade,
  evidence_id      uuid references public.evidence_items (id) on delete set null,
  body             text not null check (char_length(body) between 1 and 5000),
  created_at       timestamptz not null default now()
);
create index investigation_notes_inv_idx on public.investigation_notes (investigation_id, created_at);

-- ---------------------------------------------------------------------
-- Incident response
-- ---------------------------------------------------------------------
create table public.incidents (
  id                   uuid primary key default gen_random_uuid(),
  owner_id             uuid references public.profiles (id) on delete cascade,
  is_template          boolean not null default false,
  template_id          uuid references public.incidents (id) on delete set null,
  reference            text not null,
  title                text not null,
  category             text not null check (category in
                         ('account_compromise', 'malware', 'phishing', 'data_exposure',
                          'unauthorised_access', 'policy_violation', 'denial_of_service', 'other')),
  severity             text not null check (severity in ('low', 'medium', 'high', 'critical')),
  stage                text not null default 'alert_received' check (stage in
                         ('alert_received', 'triage', 'investigation', 'evidence_collection',
                          'impact_assessment', 'containment_planning', 'recovery_planning',
                          'resolution', 'lessons_learned')),
  status               text generated always as (
                         case when stage in ('resolution', 'lessons_learned')
                              then 'resolved' else 'open' end) stored,
  assigned_analyst     text not null default 'You',
  summary              text not null,
  related_alert_id     bigint references public.generated_alerts (id) on delete set null,
  impact_assessment    text,
  containment_plan     text,
  recovery_plan        text,
  resolution_summary   text,
  lessons_learned      text,
  recommendations      text,
  detected_at          timestamptz not null default now(),
  resolved_at          timestamptz,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  check ((is_template and owner_id is null) or (not is_template and owner_id is not null)),
  unique (owner_id, template_id)
);
create index incidents_owner_idx on public.incidents (owner_id, updated_at desc);

create table public.incident_updates (
  id          bigint generated always as identity primary key,
  incident_id uuid not null references public.incidents (id) on delete cascade,
  user_id     uuid references public.profiles (id) on delete set null,
  from_stage  text,
  to_stage    text,
  note        text check (char_length(note) <= 5000),
  created_at  timestamptz not null default now(),
  check (note is not null or to_stage is not null)
);
create index incident_updates_incident_idx on public.incident_updates (incident_id, created_at);

-- ---------------------------------------------------------------------
-- Network lab + lab submissions
-- ---------------------------------------------------------------------
create table public.network_lab_sessions (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references public.profiles (id) on delete cascade,
  lab_exercise_id uuid references public.lab_exercises (id) on delete set null,
  topology_key    text not null,
  state           jsonb not null default '{}'::jsonb,
  started_at      timestamptz not null default now(),
  completed_at    timestamptz
);
create index network_lab_sessions_user_idx on public.network_lab_sessions (user_id);

create table public.lab_submissions (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references public.profiles (id) on delete cascade,
  lab_exercise_id uuid not null references public.lab_exercises (id) on delete cascade,
  answers         jsonb not null check (jsonb_typeof(answers) = 'object'),
  score           integer not null check (score >= 0),
  max_score       integer not null check (max_score > 0),
  is_correct      boolean not null,
  feedback        jsonb not null default '[]'::jsonb,
  created_at      timestamptz not null default now(),
  check (score <= max_score)
);
create index lab_submissions_user_idx on public.lab_submissions (user_id, created_at desc);

-- ---------------------------------------------------------------------
-- Audit log (append-only, admin-readable)
-- ---------------------------------------------------------------------
create table public.audit_logs (
  id          bigint generated always as identity primary key,
  actor_id    uuid references public.profiles (id) on delete set null,
  action      text not null,
  entity_type text not null,
  entity_id   text,
  metadata    jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now()
);
create index audit_logs_created_idx on public.audit_logs (created_at desc);
create index audit_logs_actor_idx   on public.audit_logs (actor_id);
