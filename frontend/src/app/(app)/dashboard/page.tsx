"use client";

import { Award, BookOpen, Flame, Shield } from "lucide-react";
import Link from "next/link";
import { useApi } from "@/lib/api";
import type { AlertRow, Dashboard, Profile, SocOverview } from "@/lib/types";
import { ErrorState, Loading, PageHeader, ProgressBar, SeverityBadge, SimBadge, fmtTime } from "@/components/ui";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export default function DashboardPage() {
  const me = useApi<Profile>("me");
  const dash = useApi<Dashboard>("me/dashboard");
  const soc = useApi<SocOverview>("soc/overview");

  if (dash.error) return <ErrorState message={dash.error.message} onRetry={() => dash.mutate()} />;
  if (!dash.data || !me.data) return <Loading label="Loading your dashboard" />;
  const d = dash.data;
  const queue: AlertRow[] = (soc.data?.recent_alerts ?? []).filter((a) => !a.triage_status.startsWith("closed_")).slice(0, 3);

  return (
    <>
      <PageHeader title={`${greeting()}, ${me.data.display_name.split(" ")[0]}`}
                  subtitle={soc.data ? `${soc.data.alerts.open} alerts are waiting in your SOC queue.` : undefined} />
      <div className="grid gap-5 xl:grid-cols-[1.5fr_1fr]">
        <div className="flex flex-col gap-5">
          {d.next_lesson ? (
            <section className="panel grid items-center gap-5 sm:grid-cols-[1fr_auto]">
              <div>
                <span className="text-sm text-muted">Continue learning · {d.next_lesson.course_title}</span>
                <h2 className="my-1.5 text-2xl font-semibold">{d.next_lesson.title}</h2>
                <p className="text-sm text-muted">About {d.next_lesson.estimated_minutes} minutes, then a short quiz.</p>
              </div>
              <Link href={`/academy/lessons/${d.next_lesson.id}`} className="btn-primary">Open lesson</Link>
            </section>
          ) : (
            <section className="panel"><h2 className="text-xl font-semibold">You have finished every available lesson.</h2>
              <p className="text-sm text-muted">New learning paths are being written. Meanwhile, try the SIEM lab.</p></section>
          )}

          <dl className="grid grid-cols-2 gap-y-4 sm:grid-cols-4">
            {[
              [`${d.lessons.completed}/${d.lessons.total}`, "lessons completed"],
              [String(d.stats.quizzes_passed), "quizzes passed"],
              [`${d.stats.labs_solved}/${d.stats.labs_total}`, "labs solved"],
              [String(d.stats.investigations_closed), "alerts triaged"],
            ].map(([value, label], i) => (
              <div key={label} className={`px-5 ${i % 2 === 0 ? "pl-0" : "border-l border-line"} sm:border-l sm:pl-5 ${i === 0 ? "sm:border-l-0 sm:pl-0" : ""}`}>
                <dd className="text-[34px] font-semibold leading-tight">{value}</dd><dt className="text-sm text-muted">{label}</dt>
              </div>
            ))}
          </dl>

          <section className="panel">
            <div className="panel-head"><h2>Your learning paths</h2><Link href="/academy" className="link">Browse all courses</Link></div>
            {d.courses.map((c) => (
              <Link key={c.slug} href={`/academy/${c.slug}`}
                    className="grid grid-cols-[1fr_90px_44px] items-center gap-4 border-t border-line-soft py-3.5 text-sm first:border-t-0 sm:grid-cols-[1fr_120px_52px]">
                <span><span className="block font-medium">{c.title}</span><span className="text-faint">{c.completed_lessons} of {c.total_lessons} lessons</span></span>
                <ProgressBar value={Number(c.percent_complete)} label={`${c.title} progress`} />
                <span className="text-muted">{Math.round(Number(c.percent_complete))}%</span>
              </Link>
            ))}
          </section>
        </div>

        <div className="flex flex-col gap-5">
          <section className="panel">
            <div className="panel-head"><h2>SOC queue</h2><Link href="/soc" className="link">Open SOC</Link></div>
            {!soc.data ? <Loading /> : queue.length === 0 ? <p className="text-sm text-muted">Queue clear. Every recent alert has a verdict.</p> : (
              <ul>
                {queue.map((a) => (
                  <li key={a.id} className="grid grid-cols-[76px_1fr] gap-3 border-t border-line-soft py-3 text-sm first:border-t-0">
                    <SeverityBadge severity={a.severity} />
                    <Link href={`/siem?alert=${a.id}`} className="hover:underline">{a.title}
                      <span className="block text-faint">{a.rule_id} · {fmtTime(a.first_seen)}</span></Link>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-3"><SimBadge /></div>
          </section>

          <section className="panel flex items-center gap-4">
            <Flame className={d.streak_days ? "text-cyan" : "text-faint"} size={28} aria-hidden />
            <div><h2 className="text-[17px] font-semibold">{d.streak_days}-day streak</h2>
              <p className="text-sm text-muted">{d.streak_days ? "Learn something today to keep it going." : "Complete a lesson or lab to start a streak."}</p></div>
          </section>

          <section className="panel grid grid-cols-2 gap-4 text-sm">
            <div className="flex items-center gap-3"><Award className="text-cyan" aria-hidden />
              <span><b className="block text-lg">{d.stats.achievements_earned}/{d.stats.achievements_total}</b>achievements</span></div>
            <div className="flex items-center gap-3"><Shield className="text-electric" aria-hidden />
              <span><b className="block text-lg">{d.stats.incidents_open}</b>incidents open</span></div>
            <div className="col-span-2 flex items-center gap-3"><BookOpen className="text-muted" aria-hidden />
              <span>Average quiz score: <b>{d.stats.avg_quiz_score ? `${d.stats.avg_quiz_score}%` : "no quizzes yet"}</b></span></div>
          </section>
        </div>
      </div>
    </>
  );
}
