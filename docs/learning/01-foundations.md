# Learning notes 01 — Foundations: database security, synthetic data, detections

These notes walk through the three most important things built in this first session.
Each section follows the same pattern: what, why, technology, code, commands, expected output,
common errors, a small exercise, and a recap.

---

## Lesson A — Row Level Security (RLS): how one database keeps every learner's work private

**1. What we are doing.** Making PostgreSQL itself refuse to show one learner another learner's
investigations, notes, incidents or progress.

**2. Why.** If privacy lives only in API code, one forgotten `WHERE user_id = ...` leaks data.
With RLS, the database adds that filter to *every* query automatically. It is defence in depth.

**3–4. Technology and role.** PostgreSQL RLS policies + Supabase-style roles
(`anon`, `authenticated`, `service_role`) + `auth.uid()`, which returns the signed-in user's id.

**5. The code** (`database/migrations/0003_rls_and_grants.sql`):

```sql
alter table public.investigations enable row level security;     -- (a)

create policy investigations_own on public.investigations
  for all to authenticated                                          -- (b)
  using      (user_id = (select auth.uid()))                        -- (c)
  with check (user_id = (select auth.uid()));                       -- (d)
```

**6. Important lines.**
* (a) Turns RLS on. From now on: *no matching policy = no rows*.
* (b) The policy applies to every operation (`select/insert/update/delete`) for signed-in users.
* (c) `using` filters rows you can **see or change**: only rows where `user_id` is you.
* (d) `with check` validates rows you **write**: you cannot insert a row with someone else's id.
* `(select auth.uid())` is wrapped in `select` so Postgres computes it once, not per row.

And how the API applies it (`backend/app/db.py`):

```python
conn.execute(text("select set_config('request.jwt.claims', :claims, true)"), {"claims": json.dumps(claims)})
conn.execute(text("set local role authenticated"))
```

The `true` / `local` mean "only for this transaction", so a reused connection never keeps the
previous learner's identity.

**7. Commands.**
```bash
cd backend
pytest tests/test_auth_and_rls.py -q
```

**8. Expected output.** `31 passed`.

**9. Common errors.**
* `permission denied for table ...` → the role has no GRANT. RLS policies only matter *after* a grant exists.
* `new row violates row-level security policy` → your `with check` refused the write (often correct!).
* Seeing **zero rows** unexpectedly → RLS is on but no policy matches. Check the claims are set.
* `invalid input syntax for type json` from `auth.uid()` → after a transaction ends Postgres resets
  custom settings to an **empty string**, not NULL. We hit this exact bug and fixed it with `nullif(..., '')`.

**10. Exercise.** In `test_auth_and_rls.py`, `test_rls_hides_other_learners_rows` checks four tables.
Add `network_lab_sessions` to the list, run the test, and explain in one sentence why it passes.

**11. Recap.** GRANTs decide *which tables*; RLS policies decide *which rows*. The API runs every
request as the low-privilege `authenticated` role, so even buggy endpoint code cannot cross between learners.

---

## Lesson B — Why answer keys live in a table learners cannot read

**1–2. What and why.** With Supabase, the browser holds a public key that can query the database
directly. If quiz answers sat in the `questions` table, any learner could read them with one request,
and could also `INSERT` a 100% score for themselves.

**3–4. Technology.** A separate `question_answer_keys` table with RLS on and **no** learner policy,
plus a `SECURITY DEFINER` function that grades on the server.

**5. Code** (`database/migrations/0002_functions_triggers.sql`, shortened):

```sql
create or replace function public.submit_quiz_attempt(p_quiz_id uuid, p_answers jsonb)
returns jsonb
language plpgsql security definer set search_path = ''   -- (a) (b)
as $$
declare v_user uuid := auth.uid();
begin
  if v_user is null then raise exception 'authentication required'; end if;  -- (c)
  ... count correct answers by joining question_answer_keys ...
  insert into public.quiz_attempts (...) values (v_user, ...);               -- (d)
```

**6. Important lines.**
* (a) `security definer` runs with the function owner's rights, so it *can* read the hidden keys.
* (b) `set search_path = ''` forces fully-qualified names, which blocks a classic hijacking trick.
* (c) Definer functions bypass RLS, so they must check the caller themselves.
* (d) The learner never writes the score. The function does, using `auth.uid()`.

**7–8. Command / expected output.** `pytest -k "protected_data or quiz_grading" -q` → all pass.

**9. Common errors.** Forgetting (c) turns the function into a hole; forgetting (b) triggers
security linters (and Supabase's advisor) for good reason.

**10. Exercise.** Read `submit_lab_answer`. Why does it return `explanation` only when the answer
is fully correct? (Hint: what could a learner do with the explanation after a wrong attempt?)

**11. Recap.** Never trust the client with answers or scores. Hide the data, and grade in a trusted function.

---

## Lesson C — Synthetic data and testable detections

**1–2. What and why.** Labs need realistic logs, but real logs contain real people and systems.
We generate 352 events in code, with fictional hosts (`*.corp.example`) and only reserved IP ranges.
Because the generator uses a **fixed random seed**, every run produces identical data, so tests can
demand exact results.

**3–4. Technology.** Python (`random.Random(SEED)`, `dataclasses`) for the generator; plain
Python functions for detection rules.

**5. Code** (`backend/app/detections/rules.py`, the brute-force rule):

```python
def _brute_force(events, p):
    alerts = []
    failures = [e for e in events if _is_failed_auth(e)]                          # (a)
    for (user, src), group in group_by(failures, lambda e: (e["username"], e["src_ip"])).items():  # (b)
        for burst in bursts(group, timedelta(minutes=p["window_minutes"])):       # (c)
            if len(burst) >= p["threshold"]:                                      # (d)
                alerts.append(AlertCandidate("CSA-DET-001", ...))
    return alerts
```

**6. Important lines.** (a) keep only failed logins; (b) group by *who* and *from where*;
(c) split each group into bursts within a 10-minute window; (d) 5 or more failures in a burst = alert.

**7. Command.**
```bash
cd backend
python -c "from app.labdata.events import generate_events; from app.detections.rules import run_all; print(len(run_all(generate_events())))"
```

**8. Expected output.** `18`.

**9. Common errors.**
* Rules that fire on the baseline noise (false positives). Our test `test_no_alert_is_built_from_baseline_noise` catches this.
* Time zones: all events are UTC. Mixing naive and aware datetimes raises `TypeError: can't compare offset-naive and offset-aware datetimes`.
* Linting caught a real bug here (ruff `B023`): a helper function defined inside a loop captured the loop variable.

**10. Exercise.** Change `threshold` for CSA-DET-001 from 5 to 7 in `rules.py`, then run
`pytest tests/test_dataset_and_detections.py -q`. Which test fails, and why? (Look at the S3 scenario:
how many failures did m.okafor have?) Change it back afterwards.

**11. Recap.** Deterministic synthetic data makes detections *provable*: every rule has an exact
expected count, its evidence, and a deliberate "near miss" that must not alert.
