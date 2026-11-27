"use client";

import { Clock } from "lucide-react";
import Link from "next/link";
import { useApi } from "@/lib/api";
import type { CourseSummary } from "@/lib/types";
import { ErrorState, Loading, PageHeader, ProgressBar } from "@/components/ui";

// The 14 learning paths from the platform plan. Courses that exist in the database are linked;
// the rest are shown as planned, never as clickable fake content.
const PLANNED_PATHS = [
  "Cybersecurity fundamentals", "Computer networking", "Operating system fundamentals", "Linux fundamentals",
  "Windows security", "SOC operations", "SIEM fundamentals", "Log analysis", "Network security", "Digital forensics",
  "Incident response", "Defensive security monitoring", "Cloud security fundamentals", "Security documentation",
];

export default function AcademyPage() {
  const { data, error, mutate } = useApi<CourseSummary[]>("academy/courses");
  if (error) return <ErrorState message={error.message} onRetry={() => mutate()} />;
  if (!data) return <Loading label="Loading courses" />;

  const available = new Set(data.map((c) => c.learning_path.replace(/^\d+\.\s*/, "").toLowerCase()));
  const planned = PLANNED_PATHS.filter((p) => !available.has(p.toLowerCase()));

  return (
    <>
      <PageHeader title="Cybersecurity Academy" subtitle="Short lessons in plain English. Each one ends with a quiz and a practical task." />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data.map((c) => (
          <Link key={c.id} href={`/academy/${c.slug}`} className="panel flex flex-col gap-3 hover:border-line">
            <span className="text-xs text-faint">{c.learning_path} · {c.level}</span>
            <h2 className="text-lg font-semibold">{c.title}</h2>
            <p className="flex-1 text-sm text-muted">{c.summary}</p>
            <div className="flex items-center gap-3 text-xs text-muted">
              <span>{c.completed_lessons}/{c.total_lessons} lessons</span>
              <span className="inline-flex items-center gap-1"><Clock size={12} aria-hidden /> {c.estimated_minutes} min</span>
            </div>
            <ProgressBar value={Number(c.percent_complete)} label={`${c.title} progress`} />
          </Link>
        ))}
      </div>
      {planned.length > 0 && (
        <section className="mt-10">
          <h2 className="text-[17px] font-semibold">Learning paths being written</h2>
          <p className="mt-1 text-sm text-muted">These are planned and not available yet.</p>
          <ul className="mt-3 flex flex-wrap gap-2">
            {planned.map((p) => <li key={p} className="rounded-full border border-dashed border-line px-3 py-1 text-xs text-faint">{p}</li>)}
          </ul>
        </section>
      )}
    </>
  );
}
