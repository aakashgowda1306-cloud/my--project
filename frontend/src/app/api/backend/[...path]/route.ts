import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { API_PREFIX, BACKEND_URL, SESSION_COOKIE, isSameOrigin } from "@/lib/server/session";

/**
 * Backend-for-frontend proxy: /api/backend/<path> → FastAPI /api/v1/<path>.
 * Adds the learner's token from the httpOnly cookie. Safety rules:
 *  - only known top-level API areas can be reached (allowlist),
 *  - the destination origin is fixed on the server, so the token cannot be sent elsewhere,
 *  - only the headers FastAPI needs are forwarded,
 *  - state-changing requests must come from our own origin.
 */
const ALLOWED_AREAS = new Set([
  "me", "academy", "soc", "siem", "investigations", "labs", "forensics", "network", "incidents", "admin",
]);
const SEGMENT = /^[A-Za-z0-9._-]+$/;

async function forward(request: Request, path: string[]) {
  if (!path.length || !ALLOWED_AREAS.has(path[0]) || !path.every((p) => SEGMENT.test(p) && p !== "..")) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }
  if (request.method !== "GET" && !isSameOrigin(request)) {
    return NextResponse.json({ detail: "Cross-site request blocked" }, { status: 403 });
  }
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!token) return NextResponse.json({ detail: "Not signed in" }, { status: 401 });

  const url = new URL(`${API_PREFIX}/${path.join("/")}`, BACKEND_URL);
  url.search = new URL(request.url).search;

  try {
    const upstream = await fetch(url, {
      method: request.method,
      redirect: "error",
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${token}`,
        ...(request.method !== "GET" ? { "Content-Type": "application/json" } : {}),
      },
      body: request.method === "GET" ? undefined : await request.text(),
    });
    const contentType = upstream.headers.get("content-type") ?? "application/json";
    const res = new NextResponse(await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: { "content-type": contentType, "cache-control": "no-store" },
    });
    return res;
  } catch {
    return NextResponse.json({ detail: "The learning service is not reachable. Try again in a moment." }, { status: 502 });
  }
}

type Ctx = { params: Promise<{ path: string[] }> };
export async function GET(request: Request, { params }: Ctx) { return forward(request, (await params).path); }
export async function POST(request: Request, { params }: Ctx) { return forward(request, (await params).path); }
export async function PATCH(request: Request, { params }: Ctx) { return forward(request, (await params).path); }
export async function DELETE(request: Request, { params }: Ctx) { return forward(request, (await params).path); }
