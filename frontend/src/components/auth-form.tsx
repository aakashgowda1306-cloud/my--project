"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { ApiError, authRequest } from "@/lib/api";
import { Brand, ErrorState } from "./ui";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isRegister = mode === "register";

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    const form = new FormData(e.currentTarget);
    const body = Object.fromEntries(form.entries());
    if (isRegister && body.password !== body.confirm) {
      setError("The two passwords do not match.");
      return;
    }
    delete body.confirm;
    setBusy(true);
    try {
      await authRequest(mode, body);
      // Only follow local paths, so a crafted link cannot send the learner to another site.
      // Read ?next= at submit time (not during render) so the form can be prerendered as static HTML.
      const next = new URLSearchParams(window.location.search).get("next");
      // Full page load on purpose so no data cached before sign-in survives.
      window.location.assign(next && next.startsWith("/") && !next.startsWith("//") ? next : isRegister ? "/onboarding" : "/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Try again.");
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-[420px] flex-col justify-center px-5 py-10">
      <Link href="/" className="mb-8"><Brand /></Link>
      <h1 className="text-2xl font-semibold tracking-tight">{isRegister ? "Create your free account" : "Sign in"}</h1>
      <p className="mt-1 mb-6 text-sm text-muted">
        {isRegister ? "Start with a 15-minute lesson, then your first investigation." : "Continue where you left off."}
      </p>
      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate={false}>
        {isRegister && (
          <div>
            <label htmlFor="display_name" className="label">Your name</label>
            <input id="display_name" name="display_name" className="input" required minLength={2} maxLength={60} autoComplete="name" />
          </div>
        )}
        <div>
          <label htmlFor="email" className="label">Email address</label>
          <input id="email" name="email" type="email" className="input" required autoComplete="email" />
        </div>
        <div>
          <label htmlFor="password" className="label">Password</label>
          <input id="password" name="password" type="password" className="input" required minLength={isRegister ? 10 : 1}
                 maxLength={128} autoComplete={isRegister ? "new-password" : "current-password"} aria-describedby={isRegister ? "pw-hint" : undefined} />
          {isRegister && <p id="pw-hint" className="mt-1.5 text-xs text-faint">At least 10 characters. A short phrase is easier to remember than a complex word.</p>}
        </div>
        {isRegister && (
          <div>
            <label htmlFor="confirm" className="label">Confirm password</label>
            <input id="confirm" name="confirm" type="password" className="input" required minLength={10} autoComplete="new-password" />
          </div>
        )}
        {error && <ErrorState message={error} />}
        <button type="submit" className="btn-primary h-11" disabled={busy}>
          {busy ? (isRegister ? "Creating account…" : "Signing in…") : isRegister ? "Create account" : "Sign in"}
        </button>
      </form>
      <p className="mt-6 text-sm text-muted">
        {isRegister ? "Already have an account? " : "New to Cybersec Academy? "}
        <Link className="link" href={isRegister ? "/login" : "/register"}>{isRegister ? "Sign in" : "Create a free account"}</Link>
      </p>
    </div>
  );
}
