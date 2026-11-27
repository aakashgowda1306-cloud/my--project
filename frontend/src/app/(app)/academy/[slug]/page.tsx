"use client";

import { CheckCircle2, Circle, CircleDot } from "lucide-react";
import Link from "next/link";
import { use } from "react";
import { useApi } from "@/lib/api";
import { ErrorState, Loading, PageHeader } from "@/components/ui";

type Course = {
  title: string; summary: string; learning_path: string; level: string;
  modules: { id: string; title: string; lessons: { id: string; title: string; summary: string; estimated_minutes: number;
    status: "not_started" | "in_progress" | "completed"; best_quiz_score: string | null }[] }[];
};

const STATUS_ICON = { completed: CheckCircle2, in_progress: CircleDot, not_started: Circle };
const STATUS_LABEL = { completed: "Completed", in_progress: "In progress", not_started: "Not started" };

export default function CoursePage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);
  const { data, error } = useApi<Course>(`academy/courses/${encodeURIComponent(slug)}`);
  if (error) return <ErrorState message={error.status === 404 ? "This course does not exist." : error.message} />;
  if (!data) return <Loading label="Loading course" />;

  // Number lessons continuously across modules (computed up front, not mutated during render).
  const numbers = new Map(data.modules.flatMap((m) => m.lessons).map((l, i) => [l.id, i + 1]));
  return (
    <>
      <Link href="/academy" className="link">All courses</Link>
      <div className="mt-3"><PageHeader title={data.title} subtitle={`${data.learning_path} · ${data.level}`} /></div>
      <p className="-mt-2 mb-6 max-w-[70ch] text-muted">{data.summary}</p>
      {data.modules.map((m) => (
        <section key={m.id} className="panel mb-5">
          <h2 className="mb-2 text-[17px] font-semibold">{m.title}</h2>
          <ol>
            {m.lessons.map((l) => {
              const Icon = STATUS_ICON[l.status];
              return (
                <li key={l.id} className="border-t border-line-soft first:border-t-0">
                  <Link href={`/academy/lessons/${l.id}`} className="grid grid-cols-[28px_1fr_auto] items-start gap-3 py-3.5 hover:bg-raised/50">
                    <Icon size={20} className={l.status === "completed" ? "text-cyan" : l.status === "in_progress" ? "text-electric" : "text-faint"}
                          aria-label={STATUS_LABEL[l.status]} />
                    <span><span className="font-medium">{numbers.get(l.id)}. {l.title}</span><span className="block text-sm text-muted">{l.summary}</span></span>
                    <span className="text-right text-xs text-faint">{l.estimated_minutes} min
                      {l.best_quiz_score !== null && <span className="block">Best quiz: {Math.round(Number(l.best_quiz_score))}%</span>}</span>
                  </Link>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </>
  );
}
