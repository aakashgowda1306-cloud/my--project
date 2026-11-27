import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Optimistic check only: "does a session cookie exist?". Real authorisation happens in
// FastAPI (token verification) and PostgreSQL (Row Level Security).
const SESSION_COOKIE = "csa_session";
const APP_PREFIXES = ["/dashboard", "/onboarding", "/soc", "/siem", "/academy", "/forensics", "/network",
                      "/incidents", "/achievements", "/profile", "/settings", "/admin"];
const AUTH_PAGES = ["/login", "/register"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const signedIn = request.cookies.has(SESSION_COOKIE);

  if (!signedIn && APP_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`))) {
    const url = new URL("/login", request.url);
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }
  if (signedIn && AUTH_PAGES.includes(pathname)) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
