# Learning notes 02 — The frontend and keeping your login safe

## Lesson D — Why the browser never sees your token

**1. What we are doing.** Letting the Next.js app call the FastAPI backend on behalf of a signed-in learner.

**2. Why.** The simplest approach (store the token in `localStorage` and attach it in the browser)
means any cross-site-scripting (XSS) bug can read the token and impersonate the learner. We keep the token
in an **httpOnly cookie**, which page JavaScript cannot read at all.

**3–4. Technology.** Next.js **Route Handlers** (server code inside the Next.js app) acting as a
*backend-for-frontend* (BFF), plus a **Proxy** file (called Middleware before Next.js 16) for redirects.

```
Browser ──cookie──▶ Next.js /api/backend/... ──Bearer token──▶ FastAPI ──RLS──▶ PostgreSQL
```

**5. Code** (`frontend/src/app/api/auth/[action]/route.ts`, shortened):

```ts
const res = NextResponse.json({ ok: true });
res.cookies.set("csa_session", data.access_token, {
  httpOnly: true,                                   // (a)
  secure: process.env.NODE_ENV === "production",   // (b)
  sameSite: "lax",                                  // (c)
  maxAge: data.expires_in,                          // (d)
});
```

**6. Important lines.**
* (a) JavaScript in the page cannot read this cookie — XSS cannot steal it.
* (b) In production the cookie only travels over HTTPS.
* (c) The browser does not attach it to POST requests started by *other* websites (CSRF protection).
  We add a second check: the proxy rejects state-changing requests whose `Origin` is another site.
* (d) The cookie expires when the token does.

And the proxy (`frontend/src/app/api/backend/[...path]/route.ts`) only forwards to an **allowlist** of API
areas, to a **fixed** backend origin, with `redirect: "error"` — so nobody can trick it into sending
your token to another server.

**7. Commands.**
```bash
cd frontend && npm run build && npx next start      # web app on :3000 (API must run on :8000)
node ../tests/e2e/mvp-smoke.cjs                      # from the repo root
```

**8. Expected output.** `28/28 checks passed`, including
`PASS  token is not readable by page JavaScript` and `PASS  proxy blocks cross-site state-changing requests`.

**9. Common errors we actually hit while building this.**
* *"Cannot apply unknown utility class `btn`"* — Tailwind 4 cannot `@apply` a class you defined yourself in the same layer.
* *"usePathname() in a Client Component outside of `<Suspense>`"* — with Cache Components, anything that reads
  the current request (URL, cookies) must be inside a Suspense boundary.
* **Onboarding loop** — after saving onboarding, the shell still had the *cached* old profile and sent the learner
  back. Fix: update the cache with the server's response (`mutate("me", updated)`) before navigating.
* *EADDRINUSE* — an old server was still running on port 3000 and serving an older build.

**10. Exercise.** Open DevTools → Application → Cookies while signed in. Find `csa_session` and check the
**HttpOnly** column. Then type `document.cookie` in the Console. Why is `csa_session` missing from the output?

**11. Recap.** Tokens live in httpOnly cookies, the Next.js server attaches them, and a strict allowlist
proxy forwards requests. The browser can use the API without ever being able to leak the key to it.
