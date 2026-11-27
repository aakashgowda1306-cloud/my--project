"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { mutate } from "swr";
import { ApiError, apiSend, useApi } from "@/lib/api";
import type { Profile } from "@/lib/types";
import { ErrorState, Loading } from "@/components/ui";

const LEVELS = [
  { value: "beginner", title: "I'm new to cybersecurity", text: "Start with the fundamentals and networking." },
  { value: "intermediate", title: "I know the basics", text: "I understand networks and want hands-on labs." },
  { value: "advanced", title: "I've done some security work", text: "Take me straight to investigations." },
] as const;

const GOALS = ["Become a SOC analyst", "Pass a security course or certification", "Build a cybersecurity portfolio", "Understand how attacks are detected"];

export default function Onboarding() {
  const router = useRouter();
  const { data: me } = useApi<Profile>("me");
  const [level, setLevel] = useState<(typeof LEVELS)[number]["value"]>("beginner");
  const [goal, setGoal] = useState(GOALS[0]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!me) return <Loading />;

  async function finish() {
    setBusy(true);
    try {
      const updated = await apiSend<Profile>("me", "PATCH", { experience_level: level, learning_goal: goal, onboarding_completed: true });
      // Replace the cached profile so the app shell sees onboarding as done (otherwise it would send us back here).
      await mutate("me", updated, { revalidate: false });
      router.replace("/dashboard");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not save your choices.");
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold tracking-tight">Welcome, {me.display_name}</h1>
      <p className="mt-1 text-muted">Two quick questions so your dashboard suggests the right first lesson.</p>

      <fieldset className="mt-8">
        <legend className="mb-3 font-semibold">How much cybersecurity have you done?</legend>
        <div className="grid gap-3">
          {LEVELS.map((l) => (
            <label key={l.value} className={`flex cursor-pointer gap-3 rounded-xl border p-4 ${level === l.value ? "border-electric bg-electric/10" : "border-line bg-surface"}`}>
              <input type="radio" name="level" value={l.value} checked={level === l.value} onChange={() => setLevel(l.value)} className="mt-1 accent-[#3d7bff]" />
              <span><span className="block font-medium">{l.title}</span><span className="text-sm text-muted">{l.text}</span></span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="mt-8">
        <legend className="mb-3 font-semibold">What is your main goal?</legend>
        <div className="flex flex-wrap gap-2">
          {GOALS.map((g) => (
            <button key={g} type="button" className="chip h-9 text-sm" aria-pressed={goal === g} onClick={() => setGoal(g)}>{g}</button>
          ))}
        </div>
      </fieldset>

      <div className="mt-8 rounded-xl border border-dashed border-line p-4 text-sm text-muted">
        Every lab uses <strong className="text-text">simulated data</strong> about a fictional company. Nothing you do here touches a real system.
      </div>
      {error && <div className="mt-4"><ErrorState message={error} /></div>}
      <button className="btn-primary mt-6 h-11" onClick={finish} disabled={busy}>{busy ? "Saving…" : "Go to my dashboard"}</button>
    </div>
  );
}
