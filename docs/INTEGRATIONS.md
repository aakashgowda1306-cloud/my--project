# Integration status

Checked on 2026-11-27 from the cloud build environment. "Verified" means the service itself
confirmed the action.

| Integration | Status | Evidence / limitation | What unblocks it |
|---|---|---|---|
| **GitHub** | Working | Authenticated as the repository owner; commits are pushed to branch `claude/cybersec-academy-platform-6nus1x`. | — |
| **Figma** | Partly blocked | A file **was created**: "Cybersec Academy — Product Design System" (key `LYqOxOtmpfZjulZhO4OMig`). The **first write** to it was refused: *"You've reached the Figma MCP tool call limit on the Starter plan."* The account has a **View** seat on a Starter team. The file is currently empty. | Wait for the plan's MCP quota to reset, or upgrade the Figma plan / seat. Meanwhile the design system lives in `design/tokens/tokens.css` and the screens in `design/mockups/` (rendered to `design/screenshots/`). They can be imported into Figma later. |
| **Supabase** | Blocked on token | You approved the project (target organisation from your dashboard link). This repository now has its own cloud environment that allows `api.supabase.com`, and a credential was saved for it, but Supabase rejects it: *401 "JWT could not be decoded"*. | Save a **personal access token** (starts with `sbp_`, Supabase → Account → Access Tokens) in the environment's network secrets for `api.supabase.com`, replacing the current value. Then the project can be created, migrated and seeded from here. |
| **Vercel** | Not available | The Vercel connector failed to connect (network proxy refused the host), and `api.vercel.com` is blocked. | Allow Vercel hosts in the environment, or import the GitHub repository from the Vercel dashboard yourself. |
| **Docker** | Client only | The Docker CLI is installed, but no Docker daemon is running here, so images cannot be built in this environment. | Build locally with Docker Desktop: `docker compose -f docker/docker-compose.yml up --build`. |
| **PostgreSQL** | Working | Local PostgreSQL 16 is used for development and for all tests, with a shim that reproduces Supabase's `auth.uid()` behaviour. | — |
| **Canva / ElevenLabs** | Connected, not used yet | Relevant to Phase 13 (video narration and visuals). Generations spend account credits, so they will only be used with your approval. | Phase 13 |
