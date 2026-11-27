"use client";

import { useState } from "react";
import { ApiError, apiSend, useApi } from "@/lib/api";
import type { AlertDetail, Investigation } from "@/lib/types";
import { ErrorState, Loading, SeverityBadge, fmtTime } from "./ui";

const VERDICTS = [
  { value: "closed_true_positive", label: "True positive", help: "Malicious activity. It should become an incident." },
  { value: "closed_benign", label: "Expected activity", help: "Real and authorised (for example an approved change)." },
  { value: "closed_false_positive", label: "False positive", help: "The rule fired on something it was not meant to catch." },
];

const QUESTIONS: [keyof AlertDetail["rule"], string][] = [
  ["what_detected", "What was detected?"], ["why_it_matters", "Why does it matter?"],
  ["evidence_guidance", "What evidence supports it?"], ["analyst_steps", "What should you investigate?"],
  ["defensive_response", "What is the defensive response?"],
];

export function AlertDetailPanel({ alertId, onChanged }: { alertId: number; onChanged: () => void }) {
  const { data: alert, error, mutate } = useApi<AlertDetail>(`siem/alerts/${alertId}`);
  const invId = alert?.investigation?.id;
  const inv = useApi<Investigation>(invId ? `investigations/${invId}` : null);
  const [note, setNote] = useState("");
  const [verdict, setVerdict] = useState(VERDICTS[0].value);
  const [summary, setSummary] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  if (error) return <ErrorState message={error.message} />;
  if (!alert) return <Loading label="Loading alert" />;

  async function run(action: () => Promise<unknown>, ok: string) {
    setBusy(true); setMessage(null);
    try {
      await action();
      await Promise.all([mutate(), inv.mutate()]);
      onChanged();
      setMessage({ kind: "ok", text: ok });
    } catch (e) {
      setMessage({ kind: "error", text: e instanceof ApiError ? e.message : "That did not work. Try again." });
    } finally { setBusy(false); }
  }

  const closed = alert.investigation?.status.startsWith("closed_");

  return (
    <div className="flex flex-col gap-5">
      <div>
        <SeverityBadge severity={alert.severity} />
        <h2 className="mt-1.5 text-lg font-semibold">{alert.title}</h2>
        <p className="mt-1 text-sm text-muted">{alert.summary}</p>
        <dl className="mt-3 grid grid-cols-[110px_1fr] gap-x-3 gap-y-1.5 text-sm">
          <dt className="text-faint">Rule</dt><dd><span className="font-mono text-xs">{alert.rule.id}</span> {alert.rule.name}</dd>
          <dt className="text-faint">MITRE ATT&amp;CK</dt><dd>{alert.rule.mitre_technique_id} {alert.rule.mitre_technique_name} ({alert.rule.mitre_tactic})</dd>
          <dt className="text-faint">First seen</dt><dd>{fmtTime(alert.first_seen)} UTC</dd>
          <dt className="text-faint">Events</dt><dd>{alert.event_count}</dd>
        </dl>
      </div>

      <details className="rounded-lg border border-line-soft bg-abyss/40 p-3" open>
        <summary className="cursor-pointer text-sm font-semibold">Analyst questions</summary>
        <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm">
          {QUESTIONS.map(([key, q]) => (
            <li key={key}><b className="font-medium">{q}</b><span className="block text-muted">{String(alert.rule[key])}</span></li>
          ))}
        </ol>
      </details>

      <section>
        <h3 className="mb-2 text-sm font-semibold">Evidence ({alert.evidence.length} {alert.evidence.length === 1 ? "event" : "events"})</h3>
        <ul className="max-h-64 space-y-1.5 overflow-y-auto pr-1">
          {alert.evidence.map((e) => (
            <li key={e.id} className="rounded-md border border-line-soft bg-abyss/40 px-3 py-2 font-mono text-[12px] leading-5">
              <span className="text-faint">#{e.id} {fmtTime(e.event_time, false)} {e.host.replace(".corp.example", "")}</span>
              <span className="block break-words">{e.message}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="border-t border-line-soft pt-4">
        <h3 className="mb-2 text-sm font-semibold">Your investigation</h3>
        {!alert.investigation ? (
          <button className="btn-primary" disabled={busy}
                  onClick={() => run(() => apiSend("investigations", "POST", { alert_id: alert.id }), "Investigation started.")}>
            Start investigation
          </button>
        ) : (
          <div className="flex flex-col gap-4">
            <p className="text-sm">Status: <b>{alert.investigation.status.replaceAll("_", " ")}</b></p>
            {inv.data?.notes?.length ? (
              <ul className="space-y-2">{inv.data.notes.map((n) => (
                <li key={n.id} className="rounded-md bg-raised px-3 py-2 text-sm"><span className="block text-xs text-faint">{fmtTime(n.created_at)}</span>{n.body}</li>
              ))}</ul>
            ) : <p className="text-sm text-muted">No notes yet. Write down what you checked and what you found.</p>}
            <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); if (note.trim())
              run(() => apiSend(`investigations/${alert.investigation!.id}/notes`, "POST", { body: note }).then(() => setNote("")), "Note added."); }}>
              <label htmlFor="note" className="label">Add a note</label>
              <textarea id="note" className="input h-20 py-2" value={note} onChange={(e) => setNote(e.target.value)} maxLength={5000} />
              <button className="btn-ghost self-start" disabled={busy || !note.trim()}>Add note</button>
            </form>
            {!closed && (
              <form className="flex flex-col gap-2 rounded-lg border border-line-soft p-3" onSubmit={(e) => { e.preventDefault();
                run(() => apiSend(`investigations/${alert.investigation!.id}`, "PATCH", { status: verdict, summary }), "Investigation closed."); }}>
                <fieldset>
                  <legend className="label">Verdict</legend>
                  {VERDICTS.map((v) => (
                    <label key={v.value} className="flex gap-2 py-1 text-sm">
                      <input type="radio" name="verdict" value={v.value} checked={verdict === v.value} onChange={() => setVerdict(v.value)} className="mt-1 accent-[#3d7bff]" />
                      <span><b className="font-medium">{v.label}</b> <span className="text-muted">— {v.help}</span></span>
                    </label>
                  ))}
                </fieldset>
                <label htmlFor="summary" className="label">Summary (why you chose this verdict)</label>
                <textarea id="summary" required minLength={10} className="input h-24 py-2" value={summary} onChange={(e) => setSummary(e.target.value)} />
                <button className="btn-primary self-start" disabled={busy || summary.trim().length < 10}>Close investigation</button>
              </form>
            )}
            {closed && alert.investigation.summary && <p className="rounded-md bg-raised px-3 py-2 text-sm"><b>Your summary:</b> {alert.investigation.summary}</p>}
          </div>
        )}
        {message && <p role="status" className={`mt-3 text-sm ${message.kind === "ok" ? "text-cyan" : "text-sev-critical"}`}>{message.text}</p>}
      </section>
    </div>
  );
}
