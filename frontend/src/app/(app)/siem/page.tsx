"use client";

import { Play, Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { ApiError, apiSend, useApi } from "@/lib/api";
import type { AlertRow, DetectionRule, EventPage, SecurityEvent, Severity } from "@/lib/types";
import { AlertDetailPanel } from "@/components/alert-detail";
import { ErrorState, Loading, PageHeader, SeverityBadge, SimBadge, fmtTime } from "@/components/ui";

type Tab = "events" | "alerts" | "rules";
const TABS: { key: Tab; label: string }[] = [
  { key: "events", label: "Event explorer" }, { key: "alerts", label: "Alert queue" }, { key: "rules", label: "Detection rules" },
];

export default function SiemPage() {
  return <Suspense fallback={<Loading />}><Siem /></Suspense>;
}

function Siem() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const tab: Tab = params.get("alert") ? "alerts" : ((params.get("tab") as Tab) ?? "events");
  const setTab = (t: Tab) => router.replace(`${pathname}?tab=${t}`, { scroll: false });

  return (
    <>
      <PageHeader title="SIEM Investigation Lab" subtitle="Search simulated Windows, Linux, VPN, web and firewall events" actions={<SimBadge />} />
      <div role="tablist" aria-label="SIEM views" className="mb-5 flex gap-1 overflow-x-auto border-b border-line-soft">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => setTab(t.key)}
                  className={`-mb-px whitespace-nowrap border-b-2 px-3 py-2.5 text-sm ${tab === t.key ? "border-electric text-text" : "border-transparent text-muted hover:text-text"}`}>
            {t.label}
          </button>
        ))}
      </div>
      {tab === "events" && <EventsTab />}
      {tab === "alerts" && <AlertsTab selected={params.get("alert") ? Number(params.get("alert")) : null} />}
      {tab === "rules" && <RulesTab />}
    </>
  );
}

/* ------------------------------------------------------------------ Event explorer */
const SOURCES = ["windows", "linux", "authentication", "network", "application"];
const SEVS: Severity[] = ["critical", "high", "medium", "low", "info"];

function EventsTab() {
  const [draft, setDraft] = useState("");
  const [q, setQ] = useState("");
  const [source, setSource] = useState<string | null>(null);
  const [sevs, setSevs] = useState<Severity[]>([]);
  const [outcome, setOutcome] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<SecurityEvent | null>(null);

  const qs = new URLSearchParams({ page: String(page), page_size: "25" });
  if (q) qs.set("q", q);
  if (source) qs.set("source", source);
  if (outcome) qs.set("outcome", outcome);
  sevs.forEach((s) => qs.append("severity", s));
  const { data, error, isLoading } = useApi<EventPage>(`siem/events?${qs}`, { keepPreviousData: true });

  const submit = (e: FormEvent) => { e.preventDefault(); setQ(draft.trim()); setPage(1); };
  const toggleSev = (s: Severity) => { setSevs((cur) => cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s]); setPage(1); };
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_380px]">
      <div className="min-w-0">
        <form onSubmit={submit} className="mb-3 flex gap-2" role="search">
          <label htmlFor="siem-q" className="sr-only">Search events</label>
          <div className="relative flex-1">
            <Search size={16} className="absolute top-3.5 left-3 text-faint" aria-hidden />
            <input id="siem-q" className="input pl-9 font-mono" placeholder="IP, host, user, event code or text — e.g. 203.0.113.45"
                   value={draft} onChange={(e) => setDraft(e.target.value)} maxLength={100} />
          </div>
          <button className="btn-primary h-11">Search</button>
        </form>
        <div className="mb-4 flex flex-wrap gap-2" aria-label="Filters">
          {SOURCES.map((s) => (
            <button key={s} className="chip" aria-pressed={source === s} onClick={() => { setSource(source === s ? null : s); setPage(1); }}>{s}</button>
          ))}
          <span className="mx-1 w-px bg-line" aria-hidden />
          {SEVS.map((s) => <button key={s} className="chip" aria-pressed={sevs.includes(s)} onClick={() => toggleSev(s)}>{s}</button>)}
          <span className="mx-1 w-px bg-line" aria-hidden />
          {["failure", "success"].map((o) => (
            <button key={o} className="chip" aria-pressed={outcome === o} onClick={() => { setOutcome(outcome === o ? null : o); setPage(1); }}>{o}</button>
          ))}
        </div>

        {error && <ErrorState message={error.message} />}
        {isLoading && !data && <Loading label="Searching" />}
        {data && (
          <section className="panel px-0 py-4">
            <div className="mb-2 flex justify-between px-5 text-sm text-muted" aria-live="polite">
              <span>{data.total} events match</span><span>Page {data.page} of {pages}</span>
            </div>
            {data.items.length === 0 ? <p className="px-5 py-6 text-sm text-muted">No events match. Remove a filter or search for a different value.</p> : (
              <>
                {/* Desktop: table */}
                <table className="data-table hidden md:table">
                  <thead><tr><th className="pl-5">Time (UTC)</th><th>Severity</th><th>Source</th><th>Host</th><th>Message</th></tr></thead>
                  <tbody>{data.items.map((e) => (
                    <tr key={e.id} onClick={() => setSelected(e)} className={`cursor-pointer hover:bg-raised ${selected?.id === e.id ? "bg-raised" : ""}`}>
                      <td className="whitespace-nowrap pl-5 font-mono text-xs text-muted">{fmtTime(e.event_time)}</td>
                      <td><SeverityBadge severity={e.severity} /></td>
                      <td className="text-muted">{e.source}</td>
                      <td className="whitespace-nowrap">{e.host.replace(".corp.example", "")}</td>
                      <td className="font-mono text-xs leading-5">
                        <button className="text-left hover:underline" onClick={() => setSelected(e)}>{e.message}</button>
                      </td>
                    </tr>
                  ))}</tbody>
                </table>
                {/* Mobile: cards */}
                <ul className="space-y-2 px-3 md:hidden">{data.items.map((e) => (
                  <li key={e.id}>
                    <button onClick={() => setSelected(e)} className={`w-full rounded-lg border p-3 text-left ${selected?.id === e.id ? "border-electric" : "border-line-soft"}`}>
                      <span className="mb-1 flex justify-between text-xs text-faint"><SeverityBadge severity={e.severity} />{fmtTime(e.event_time)}</span>
                      <span className="block font-mono text-[12.5px] leading-5">{e.message}</span>
                      <span className="mt-1 block text-xs text-faint">{e.host}</span>
                    </button>
                  </li>
                ))}</ul>
                <div className="mt-3 flex justify-between px-5">
                  <button className="btn-ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
                  <button className="btn-ghost" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</button>
                </div>
              </>
            )}
          </section>
        )}
      </div>
      <aside className="panel h-fit xl:sticky xl:top-6" aria-label="Event details">
        {!selected ? <p className="text-sm text-muted">Select an event to see every field.</p> : (
          <>
            <SeverityBadge severity={selected.severity} />
            <h2 className="mt-1.5 mb-3 font-semibold">{selected.action.replaceAll("_", " ")} · {selected.outcome}</h2>
            <dl className="grid grid-cols-[100px_1fr] gap-x-3 gap-y-1.5 text-sm">
              {([["Event", `#${selected.id} · ${selected.event_code}`], ["Time", `${fmtTime(selected.event_time)} UTC`], ["Source", selected.source],
                 ["Host", selected.host], ["User", selected.username], ["Source IP", selected.src_ip], ["Dest.", selected.dst_ip && `${selected.dst_ip}:${selected.dst_port ?? ""}`],
                 ["Process", selected.process_name]] as [string, string | null][]).filter(([, v]) => v).map(([k, v]) => (
                <div key={k} className="contents"><dt className="text-faint">{k}</dt><dd className="break-all font-mono text-xs leading-5">{v}</dd></div>
              ))}
            </dl>
            <h3 className="mt-4 mb-1.5 text-sm font-semibold">Message</h3>
            <p className="break-words rounded-md bg-abyss/50 p-2.5 font-mono text-xs leading-5">{selected.message}</p>
            {selected.command_line && <><h3 className="mt-4 mb-1.5 text-sm font-semibold">Command line</h3>
              <p className="break-all rounded-md bg-abyss/50 p-2.5 font-mono text-xs leading-5">{selected.command_line}</p></>}
            <h3 className="mt-4 mb-1.5 text-sm font-semibold">Raw fields</h3>
            <pre className="overflow-x-auto rounded-md bg-abyss/50 p-2.5 font-mono text-xs">{JSON.stringify(selected.raw, null, 2)}</pre>
          </>
        )}
      </aside>
    </div>
  );
}

/* ------------------------------------------------------------------ Alert queue */
function AlertsTab({ selected }: { selected: number | null }) {
  const router = useRouter();
  const { data, error, mutate } = useApi<AlertRow[]>("siem/alerts");
  const [current, setCurrent] = useState<number | null>(selected);
  const choose = (id: number) => { setCurrent(id); router.replace(`/siem?alert=${id}`, { scroll: false }); };

  if (error) return <ErrorState message={error.message} />;
  if (!data) return <Loading label="Loading alerts" />;
  const active = current ?? data[0]?.id ?? null;

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_460px]">
      <section className="panel px-0 py-3">
        <ul>{data.map((a) => (
          <li key={a.id}>
            <button onClick={() => choose(a.id)} aria-current={active === a.id}
                    className={`grid w-full grid-cols-[84px_1fr] gap-3 border-t border-line-soft px-5 py-3 text-left text-sm first:border-t-0 sm:grid-cols-[84px_1fr_130px] ${active === a.id ? "bg-raised" : "hover:bg-raised/60"}`}>
              <SeverityBadge severity={a.severity} />
              <span>{a.title}<span className="block text-xs text-faint">{a.rule_id} · {a.mitre_technique_id} · {fmtTime(a.first_seen)}</span></span>
              <span className="col-start-2 text-xs text-muted sm:col-start-auto sm:text-right">{a.triage_status.replaceAll("_", " ")}</span>
            </button>
          </li>
        ))}</ul>
      </section>
      <aside className="panel h-fit xl:sticky xl:top-6" aria-label="Alert investigation">
        {active ? <AlertDetailPanel key={active} alertId={active} onChanged={() => mutate()} /> : <p className="text-sm text-muted">No alerts.</p>}
      </aside>
    </div>
  );
}

/* ------------------------------------------------------------------ Detection rules */
type RunResult = { rule_id: string; events_scanned: number; match_count: number;
  matches: { title: string; severity: Severity; summary: string; evidence_event_ids: number[] }[] };

function RulesTab() {
  const { data, error } = useApi<DetectionRule[]>("siem/rules");
  const [results, setResults] = useState<Record<string, RunResult | string>>({});
  const [running, setRunning] = useState<string | null>(null);

  async function runRule(id: string) {
    setRunning(id);
    try {
      const res = await apiSend<RunResult>(`siem/rules/${id}/run`, "POST");
      setResults((r) => ({ ...r, [id]: res }));
    } catch (e) {
      setResults((r) => ({ ...r, [id]: e instanceof ApiError ? e.message : "Rule run failed" }));
    } finally {
      setRunning(null);
    }
  }

  if (error) return <ErrorState message={error.message} />;
  if (!data) return <Loading label="Loading rules" />;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {data.map((r) => {
        const res = results[r.id];
        return (
          <article key={r.id} className="panel">
            <div className="flex items-start justify-between gap-3">
              <div>
                <span className="font-mono text-xs text-muted">{r.id} · {r.mitre_technique_id} {r.mitre_technique_name}</span>
                <h2 className="mt-0.5 font-semibold">{r.name}</h2>
              </div>
              <SeverityBadge severity={r.severity} />
            </div>
            <p className="mt-2 text-sm text-muted">{r.what_detected}</p>
            <p className="mt-2 text-sm"><b className="font-medium">Why it matters: </b><span className="text-muted">{r.why_it_matters}</span></p>
            <div className="mt-3 flex items-center gap-3">
              <button className="btn-ghost" onClick={() => runRule(r.id)} disabled={running === r.id}>
                <Play size={14} aria-hidden /> {running === r.id ? "Running…" : "Run rule on the dataset"}
              </button>
              <span className="text-xs text-faint">{r.alert_count} stored alerts</span>
            </div>
            {typeof res === "string" && <div className="mt-3"><ErrorState message={res} /></div>}
            {res && typeof res === "object" && (
              <div className="mt-3 rounded-lg border border-line-soft bg-abyss/40 p-3 text-sm" role="status">
                Scanned {res.events_scanned} events · <b>{res.match_count} match{res.match_count === 1 ? "" : "es"}</b>
                <ul className="mt-2 space-y-1.5">{res.matches.map((m, i) => (
                  <li key={i}><SeverityBadge severity={m.severity} /> {m.summary}
                    <span className="block font-mono text-xs text-faint">evidence: {m.evidence_event_ids.slice(0, 8).map((x) => `#${x}`).join(" ")}{m.evidence_event_ids.length > 8 ? " …" : ""}</span></li>
                ))}</ul>
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}
