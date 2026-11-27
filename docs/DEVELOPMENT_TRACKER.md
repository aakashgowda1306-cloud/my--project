# Development tracker

Last updated: 2026-11-27

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 01 Product architecture and requirements | **Done** | `docs/ARCHITECTURE.md`, `docs/LAB_SAFETY.md` |
| 02 UI/UX design | **In review** | Figma blocked by plan quota (see `INTEGRATIONS.md`). Tokens + 6 mockups in `design/`. **Waiting for your feedback before frontend work.** |
| 03 Repository and dev environment | **Done** | Monorepo, `.gitignore`, `.gitattributes`, `.env.example`, Dockerfile/compose (not build-tested: no Docker daemon here) |
| 04 Database and authentication | **Done locally** | 3 migrations, RLS on all 28 tables. Not yet applied to Supabase (no access). |
| 05 Next.js frontend foundation | Not started | Blocked on design approval |
| 06 FastAPI backend | **Done for MVP scope** | All MVP routes implemented and tested |
| 07 SOC Operations Centre | Backend done | `/soc/overview`, metrics computed from data |
| 08 SIEM Investigation Lab | Backend done | 352 events, search/filter/paging, 10 rules, live rule runs, alerts, investigations |
| 09 Digital Forensics Lab | Backend done | 5 evidence files, hashes, chain of custody, timeline, hash demo |
| 10 Network Security Lab | Backend done | Topology, packet walkthrough, traffic records, subnet calculator, 3 labs |
| 11 Incident Response Centre | Backend done | 9-stage workflow enforced in the database, updates, reports |
| 12 Cybersecurity Academy | Backend + initial content | 3 of 14 learning paths have lessons; the other 11 are not yet written |
| 13 Educational video experience | Not started | |
| 14 Testing and security review | Ongoing | 72 automated tests; full review planned after frontend |
| 15 Cloud deployment | Not started | Needs Supabase + Vercel access and your approval |
| 16 Public introduction and portfolio | Not started | |

**Current phase:** 02 design review → then 05 frontend foundation.
**Next milestone:** Working Next.js app (landing, register/login, dashboard, SOC, SIEM) talking to this API.

## Test report (2026-11-27)

Command: `cd backend && pytest` (creates a fresh `cybersec_academy_test` database, applies all
migrations, seeds data). Result: **72 passed, 0 failed** in ~21 s, on PostgreSQL 16 + Python 3.13.

| File | Tests | What it proves |
|---|---|---|
| `test_dataset_and_detections.py` | 22 | ≥300 events; deterministic; ids sequential; every event synthetic with fictional hosts; only RFC 1918 / RFC 5737 IPs; all 5 log sources; **each of the 10 rules fires exactly the expected number of times on exactly the expected scenarios**; no alert built from benign noise; near-miss typos don't alert; every rule has MITRE ID + all five analyst explanations; DB counts match generator; re-running detections is idempotent |
| `test_auth_and_rls.py` | 31 | Register/login; identical errors for wrong password vs unknown email; duplicate & weak passwords rejected; passwords bcrypt-hashed; missing/forged/expired tokens rejected; login rate limit (429 after 10 failures); **learners cannot read or modify each other's investigations, notes, incidents, progress (via API and directly in SQL)**; learners cannot read answer keys or scenario labels, write scores/achievements/events, forge audit entries, promote themselves, edit chain-of-custody, add custody to shared evidence, forge incident history, or edit template incidents; anonymous users see the catalogue but not lessons; admin routes refuse students; admin role change is audited |
| `test_workflows.py` | 19 | Lessons expose no answers; quiz grading (0% and 100%); progress % calculation; achievements awarded; streak; idempotent lesson completion; onboarding; **SOC metrics equal direct DB counts**; search filters/pagination; SQL-injection-style input treated as text; live rule run; alert detail; investigation lifecycle (summary required to close, resolved count updates); lab grading incl. partial credit and case/whitespace tolerance; every lab declares its safety boundary; evidence hashes match the real files; hash & subnet tools; forensic timeline; network data; **incident workflow: cannot skip stages, documentation required, one-step rework allowed, history recorded, report generated** |

Lint: `ruff check app tests` → clean (security rules `S` enabled).

Not yet tested (needs the frontend or cloud): frontend components, mobile responsiveness,
accessibility audit, Supabase-hosted RLS, deployment smoke tests.

## Known issues and limitations

1. **Figma file is empty** because of the Starter-plan MCP limit. Designs live in `design/` for now.
2. **Supabase not connected.** Everything is tested on local Postgres with a shim reproducing Supabase auth functions; must be re-verified on a real Supabase project.
3. **Supabase JWT verification uses the HS256 JWT secret.** Newer Supabase projects can use asymmetric signing keys (JWKS); support for that will be added when connecting the real project.
4. **Login rate limiting is in-memory** (per process). On serverless hosting each instance counts separately; Supabase Auth's own limits apply in production.
5. **Docker image not build-tested** (no daemon in this environment).
6. Only 3 of the 14 requested learning paths have lessons so far.
7. Forensic evidence excerpts were written by hand to match the dataset; SSH process ids/ports in `auth_excerpt_lnx-bastion-01.log` differ slightly from the SIEM rows.
