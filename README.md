# Cybersec Academy

**Learn. Investigate. Defend. Master Cybersecurity.**

Cybersec Academy is a defensive cybersecurity learning platform. It pairs short, beginner-friendly
lessons with hands-on labs (SOC, SIEM, Digital Forensics, Network Security, Incident Response)
built on the logs, evidence and incidents of **ExampleCorp**, a fictional company. All lab data
is synthetic. See [docs/LAB_SAFETY.md](docs/LAB_SAFETY.md).

> **Status: MVP in progress.** Landing page, registration/sign-in, onboarding, dashboard, Academy,
> SOC Operations Centre and SIEM Lab work end to end. Forensics, Network and Incident Response have
> working APIs; their screens are next. See [docs/DEVELOPMENT_TRACKER.md](docs/DEVELOPMENT_TRACKER.md).

## What exists today

| Area | State |
|------|-------|
| Database (28 tables, RLS on all) | Built, tested locally |
| Synthetic SIEM dataset | 352 events, deterministic, private/documentation IPs only |
| Detection engine | 10 rules mapped to MITRE ATT&CK, 18 alerts, exact counts tested |
| REST API (FastAPI) | Auth (local mode), Academy, SOC, SIEM, investigations, forensics, network, incidents, admin |
| Academy content | 3 courses, 8 lessons, 24 quiz questions, 10 graded labs |
| Tests | 72 passing (see tracker for the report) |
| Web frontend (Next.js 16) | Landing, auth, onboarding, dashboard, Academy, SOC, SIEM — 28/28 browser checks pass |
| Deployment | Not started |

## Repository layout

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#5-repository-layout) for the full explanation.

```
frontend/             Next.js app (App Router, Tailwind, Plotly)
backend/              FastAPI app + tests
database/migrations/  SQL schema, functions, RLS (runs on Supabase unchanged)
database/local/       local-only stand-in for Supabase's auth schema
labs/                 lab datasets and evidence files
educational-content/  course catalogue and lesson Markdown
design/               design tokens, mockups and screenshots
docs/                 architecture, tracker, integrations, learning notes
docker/               Dockerfile and compose for an isolated stack
```

## Run it locally

Requirements: Python 3.12+, PostgreSQL 15+ (or Docker).

```bash
# 1. Create a database
createdb cybersec_academy

# 2. Install the backend
cd backend
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 3. Configure (never commit .env)
cp ../.env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into LOCAL_JWT_SECRET

# 4. Create the schema and load the synthetic data
python -m app.cli migrate --with-local-shim
python -m app.cli seed

# 5. Start the API and open the interactive docs
uvicorn app.main:app --reload
# → http://localhost:8000/docs
```

Then start the web app (in a second terminal):

```bash
cd frontend
cp .env.example .env.local     # BACKEND_URL=http://localhost:8000
npm install
npm run dev
# → http://localhost:3000
```

Run the tests (they create and destroy their own `cybersec_academy_test` database):

```bash
cd backend && pytest                 # 72 API, database and security tests
node tests/e2e/mvp-smoke.cjs         # 28 browser checks (API + web app must be running)
```

## Using Supabase instead of local Postgres

1. Run `database/migrations/*.sql` in order in the Supabase SQL editor (do **not** run `database/local/`).
2. Set `AUTH_MODE=supabase`, `SUPABASE_JWT_SECRET`, and `DATABASE_URL` (pooler connection string) in the backend environment.
3. Run `python -m app.cli seed` once against that database.

The service-role key and database password are server-side secrets. They never go into the
frontend or into Git.

## Documentation

* [Architecture and decisions](docs/ARCHITECTURE.md)
* [Development tracker and test report](docs/DEVELOPMENT_TRACKER.md)
* [Integration status](docs/INTEGRATIONS.md)
* [Lab safety boundary](docs/LAB_SAFETY.md)
* [Learning notes 01: database security, synthetic data, detections](docs/learning/01-foundations.md)
* [Learning notes 02: the frontend and keeping your login safe](docs/learning/02-frontend-auth.md)
