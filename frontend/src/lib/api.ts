"use client";

import useSWR, { type SWRConfiguration } from "swr";

/** Error with the HTTP status and the API's human-readable message. */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (res.status === 401 && typeof window !== "undefined") {
    // Token missing or expired: clear the cookie and send the learner to sign in.
    await fetch("/api/auth/logout", { method: "POST" });
    // Full page load on purpose: it discards every cached response from the old session.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/login?next=${encodeURIComponent(window.location.pathname)}`);
  }
  const type = res.headers.get("content-type") ?? "";
  const data = type.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = typeof data === "object" && data && "detail" in data ? data.detail : data;
    throw new ApiError(res.status, typeof detail === "string" ? detail : "Something went wrong");
  }
  return data as T;
}

/** All learner data goes through our own /api/backend proxy (cookie → Bearer token). */
export const backendUrl = (path: string) => `/api/backend/${path.replace(/^\//, "")}`;

export async function apiGet<T>(path: string): Promise<T> {
  return handle<T>(await fetch(backendUrl(path), { cache: "no-store" }));
}

export async function apiSend<T>(path: string, method: "POST" | "PATCH" | "DELETE", body?: unknown): Promise<T> {
  return handle<T>(await fetch(backendUrl(path), {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  }));
}

/** Data hook: caches, deduplicates and revalidates GET requests. */
export function useApi<T>(path: string | null, config?: SWRConfiguration<T, ApiError>) {
  return useSWR<T, ApiError>(path, apiGet, { revalidateOnFocus: false, ...config });
}

export async function authRequest(action: "login" | "register" | "logout", body?: unknown) {
  return handle<{ ok: boolean }>(await fetch(`/api/auth/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  }));
}
