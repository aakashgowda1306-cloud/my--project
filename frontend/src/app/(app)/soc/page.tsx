"use client";

import Link from "next/link";
import { useMemo } from "react";
import { useApi } from "@/lib/api";
import type { AlertRow, Severity, SocOverview } from "@/lib/types";
import { Plot } from "@/components/plot";
import { ErrorState, Loading, PageHeader, SEV_COLOR, SeverityBadge, SimBadge, fmtTime } from "@/components/ui";

const SEVERITIES: Severity[] = ["info", "low", "medium", "high", "critical"];
const DAY_MS = 86_400_000;

export default function SocPage() {
  const overview = useApi<SocOverview>("soc/overview");
  const alerts = useApi<AlertRow[]>("siem/alerts");

  // Events per day, stacked by severity — derived from the hourly timeline the API returns.
  const chart = useMemo(() => {
    if (!overview.data) return null;
    const days = Array.from(new Set(overview.data.timeline.map((b) => b.bucket.slice(0, 10)))).sort();
    return SEVERITIES.map((sev) => ({
      type: "bar" as const, name: sev[0].toUpperCase() + sev.slice(1),
      x: days.map((d) => new Date(`${d}T00:00:00Z`).toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", timeZone: "UTC" })),
      y: days.map((d) => overview.data!.timeline.filter((b) => b.severity === sev && b.bucket.startsWith(d)).reduce((n, b) => n + b.count, 0)),
      marker: { color: SEV_COLOR[sev], opacity: sev === "info" ? 0.45 : 1 },
      hovertemplate: "%{y} %{fullData.name} events<extra></extra>",
    }));
  }, [overview.data]);

  // Attack chain: alerts that share the account or address range seen in the first high-severity alert.
  const chain = useMemo(() => {
    if (!alerts.data?.length) return null;
    const markers = ["m.okafor", "203.0.113."];
    const linked = alerts.data
      .filter((a) => a.severity !== "low" && markers.some((m) => JSON.stringify(a.entity ?? {}).includes(m)))
      .sort((a, b) => a.first_seen.localeCompare(b.first_seen));
    // The axis starts at midnight UTC of the first day in the event timeline.
    const firstBucket = overview.data?.timeline[0]?.bucket;
    if (!firstBucket) return null;
    const from = new Date(`${firstBucket.slice(0, 10)}T00:00:00Z`).getTime();
    return { linked, from, span: 7 * DAY_MS };
  }, [alerts.data, overview.data]);

  if (overview.error) return <ErrorState message={overview.error.message} onRetry={() => overview.mutate()} />;
  if (!overview.data) return <Loading label="Loading the SOC" />;
  const o = overview.data;

  return (
    <>
      <PageHeader title="SOC Operations Centre" subtitle="ExampleCorp · dataset synthetic-v1 · all times UTC" actions={<SimBadge />} />

      <section aria-label="Key figures" className="mb-5 grid grid-cols-2 overflow-hidden rounded-xl border border-line-soft bg-surface md:grid-cols-5">
        <div className="col-span-2 border-b border-line-soft p-5 md:col-span-1 md:border-b-0">
          <span className="text-sm text-muted">Security events</span>
          <b className="block text-3xl font-semibold">{o.events.total}</b>
          <div className="mt-3 flex h-2 gap-0.5 overflow-hidden rounded-full" aria-hidden>
            {SEVERITIES.map((s) => <span key={s} style={{ flex: o.events.by_severity[s] ?? 0, background: SEV_COLOR[s], opacity: s === "info" ? 0.45 : 1 }} />)}
          </div>
        </div>
        {(["critical", "high", "medium"] as const).map((s) => (
          <div key={s} className="border-l border-line-soft p-5 first-of-type:border-l-0">
            <SeverityBadge severity={s} /><span className="sr-only"> alerts</span>
            <b className="block text-3xl font-semibold">{o.alerts.by_severity[s] ?? 0}</b>
            <span className="text-xs text-faint">alerts</span>
          </div>
        ))}
        <div className="border-l border-line-soft p-5">
          <span className="text-sm text-muted">Your triage</span>
          <b className="block text-3xl font-semibold">{o.alerts.resolved}<span className="text-lg text-faint"> / {o.alerts.total}</span></b>
          <span className="text-xs text-muted">closed · {o.incidents.open} incidents open</span>
        </div>
      </section>

      {chain && chain.linked.length > 0 && (
        <section className="panel mb-5">
          <div className="panel-head"><h2>Attack chain: alerts linked by account and address range</h2></div>
          <p className="max-w-[80ch] text-sm text-muted">
            Alerts sharing the account <span className="font-mono">m.okafor</span> or the range <span className="font-mono">203.0.113.0/24</span>,
            plotted across the week. Clusters show where to start investigating.
          </p>
          <div className="relative mt-4 hidden h-16 sm:block" aria-hidden>
            <div className="absolute inset-x-0 top-[30px] h-px bg-line" />
            {Array.from({ length: 7 }, (_, i) => (
              <span key={i} className="absolute top-10 -translate-x-1/2 text-xs text-faint" style={{ left: `${((i + 0.5) / 7) * 100}%` }}>
                {new Date(chain.from + i * DAY_MS).toLocaleDateString("en-GB", { weekday: "short", day: "2-digit", timeZone: "UTC" })}
              </span>
            ))}
            {chain.linked.map((a) => (
              <i key={a.id} className="absolute top-2 h-[22px] w-[3px] rounded-sm"
                 style={{ left: `${((new Date(a.first_seen).getTime() - chain.from) / chain.span) * 100}%`, background: SEV_COLOR[a.severity] }} />
            ))}
          </div>
          <ol className="mt-4 grid gap-x-5 gap-y-2.5 sm:grid-cols-2 xl:grid-cols-3">
            {chain.linked.map((a) => (
              <li key={a.id} className="border-l-2 py-1 pl-3 text-sm" style={{ borderColor: SEV_COLOR[a.severity] }}>
                <span className="flex justify-between text-xs text-faint"><span>{fmtTime(a.first_seen)}</span><span className="font-mono">{a.rule_id}</span></span>
                <Link href={`/siem?alert=${a.id}`} className="font-medium hover:underline">{a.title}</Link>
              </li>
            ))}
          </ol>
        </section>
      )}

      <div className="grid gap-5 xl:grid-cols-[1.35fr_1fr]">
        <section className="panel">
          <div className="panel-head"><h2>Events per day by severity</h2><Link href="/siem" className="link">Open in SIEM</Link></div>
          {chart && <Plot data={chart} layout={{ barmode: "stack", bargap: 0.25 }} height={420}
                          ariaLabel="Stacked bar chart of security events per day by severity" />}
        </section>
        <section className="panel">
          <div className="panel-head"><h2>Detections that fired</h2><Link href="/siem?tab=rules" className="link">All 10 rules</Link></div>
          <table className="data-table">
            <thead><tr><th>Rule</th><th>ATT&amp;CK</th><th className="text-right">Alerts</th></tr></thead>
            <tbody>
              {o.alerts.by_rule.filter((r) => r.count > 0).sort((a, b) => b.count - a.count).map((r) => (
                <tr key={r.rule_id}>
                  <td><span className="font-mono text-xs text-muted">{r.rule_id}</span><br />{r.name}</td>
                  <td className="font-mono text-xs text-muted">{r.mitre_technique_id}</td>
                  <td className="text-right">{r.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-2">
        <section className="panel">
          <div className="panel-head"><h2>Most recent alerts</h2><Link href="/siem?tab=alerts" className="link">Alert queue</Link></div>
          <ul>
            {o.recent_alerts.map((a) => (
              <li key={a.id} className="grid grid-cols-[80px_1fr_auto] items-start gap-3 border-t border-line-soft py-2.5 text-sm first:border-t-0">
                <SeverityBadge severity={a.severity} />
                <Link href={`/siem?alert=${a.id}`} className="hover:underline">{a.title}<span className="block text-xs text-faint">{fmtTime(a.first_seen)}</span></Link>
                <span className="text-xs text-muted">{a.triage_status.replaceAll("_", " ")}</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="panel">
          <div className="panel-head"><h2>Hosts with the most high-severity activity</h2></div>
          <table className="data-table">
            <thead><tr><th>Host</th><th className="text-right">High / critical</th><th className="text-right">All events</th></tr></thead>
            <tbody>{o.top_hosts.map((h) => (
              <tr key={h.host}><td className="font-mono text-xs">{h.host}</td><td className="text-right">{h.high_or_critical}</td><td className="text-right text-muted">{h.events}</td></tr>
            ))}</tbody>
          </table>
        </section>
      </div>
    </>
  );
}
