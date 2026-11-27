import { AlertTriangle, Loader2, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import type { Severity } from "@/lib/types";

const SEV_CLASS: Record<Severity, string> = {
  critical: "text-sev-critical", high: "text-sev-high", medium: "text-sev-medium", low: "text-sev-low", info: "text-sev-info",
};

/** Colour square + word: severity never relies on colour alone (accessibility). */
export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${SEV_CLASS[severity]}`}>
      <span aria-hidden className="h-2 w-2 rounded-[2px] bg-current" />
      {severity[0].toUpperCase() + severity.slice(1)}
    </span>
  );
}

export const SEV_COLOR: Record<Severity, string> = {
  critical: "#f25c6b", high: "#f59a3b", medium: "#e9c75f", low: "#7fa7e8", info: "#5f7598",
};

export function SimBadge({ children = "Simulated data" }: { children?: ReactNode }) {
  return <span className="sim-badge" title="All lab data in Cybersec Academy is synthetic">{children}</span>;
}

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5 whitespace-nowrap font-semibold">
      <span className="grid h-7 w-7 place-items-center rounded-[7px] bg-electric text-white">
        <ShieldCheck size={16} aria-hidden />
      </span>
      {!compact && "Cybersec Academy"}
    </span>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-8 text-sm text-muted">
      <Loader2 className="animate-spin" size={16} aria-hidden /> {label}…
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-sev-critical/40 bg-sev-critical/10 p-4 text-sm">
      <AlertTriangle size={18} className="mt-0.5 shrink-0 text-sev-critical" aria-hidden />
      <div className="flex-1">{message}</div>
      {onRetry && <button className="link" onClick={onRetry}>Try again</button>}
    </div>
  );
}

export function ProgressBar({ value, label }: { value: number; label: string }) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div role="progressbar" aria-label={label} aria-valuenow={Math.round(v)} aria-valuemin={0} aria-valuemax={100}
         className="h-1.5 overflow-hidden rounded-full bg-raised">
      <div className="h-full rounded-full bg-cyan" style={{ width: `${v}%` }} />
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions}
    </header>
  );
}

export const fmtTime = (iso: string, withDate = true) =>
  new Date(iso).toLocaleString("en-GB", {
    timeZone: "UTC", ...(withDate ? { weekday: "short", day: "2-digit", month: "short" } : {}),
    hour: "2-digit", minute: "2-digit", second: withDate ? undefined : "2-digit",
  });
