import "server-only";

/** Where FastAPI runs. Server-side only: the browser never talks to FastAPI directly. */
export const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
export const API_PREFIX = "/api/v1";

/** httpOnly cookie that holds the access token. JavaScript in the page cannot read it,
 *  so a cross-site-scripting bug could not steal the token. */
export const SESSION_COOKIE = "csa_session";

export const cookieOptions = (maxAgeSeconds: number) => ({
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const, // the cookie is not sent on cross-site POSTs (CSRF protection)
  path: "/",
  maxAge: maxAgeSeconds,
});

/** Reject state-changing requests that come from another website. */
export function isSameOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin) return true; // same-origin fetches from older browsers may omit Origin; SameSite still applies
  try {
    return new URL(origin).host === new URL(request.url).host;
  } catch {
    return false;
  }
}
