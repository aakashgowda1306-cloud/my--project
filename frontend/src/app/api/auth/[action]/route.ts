import { NextResponse } from "next/server";
import { API_PREFIX, BACKEND_URL, SESSION_COOKIE, cookieOptions, isSameOrigin } from "@/lib/server/session";

/**
 * POST /api/auth/login | /api/auth/register | /api/auth/logout
 * Calls FastAPI, then stores the returned token in an httpOnly cookie.
 * The token itself is never sent to browser JavaScript.
 */
export async function POST(request: Request, { params }: { params: Promise<{ action: string }> }) {
  const { action } = await params;
  if (!isSameOrigin(request)) return NextResponse.json({ detail: "Cross-site request blocked" }, { status: 403 });

  if (action === "logout") {
    const res = NextResponse.json({ ok: true });
    res.cookies.set(SESSION_COOKIE, "", { ...cookieOptions(0) });
    return res;
  }
  if (action !== "login" && action !== "register") {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON" }, { status: 400 });
  }

  try {
    const upstream = await fetch(`${BACKEND_URL}${API_PREFIX}/auth/${action}`, {
      method: "POST",
      redirect: "error",
      headers: {
        "Content-Type": "application/json",
        // Pass the learner's address on so the backend's login rate limit counts per person.
        "X-Forwarded-For": request.headers.get("x-forwarded-for") ?? "",
      },
      body: JSON.stringify(body),
    });
    const data = await upstream.json().catch(() => ({}));
    if (!upstream.ok) {
      return NextResponse.json({ detail: formatDetail(data?.detail) }, { status: upstream.status });
    }
    const res = NextResponse.json({ ok: true }, { status: upstream.status });
    res.cookies.set(SESSION_COOKIE, data.access_token, cookieOptions(data.expires_in));
    return res;
  } catch {
    return NextResponse.json({ detail: "The learning service is not reachable. Try again in a moment." }, { status: 502 });
  }
}

/** FastAPI validation errors are a list; turn them into one readable sentence. */
function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: string[]; msg?: string }) => `${d.loc?.at(-1) ?? "field"}: ${d.msg ?? "invalid"}`)
      .join("; ");
  }
  return "Request failed";
}
