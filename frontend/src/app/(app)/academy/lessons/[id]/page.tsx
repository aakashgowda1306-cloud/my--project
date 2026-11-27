"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ApiError, apiSend, useApi } from "@/lib/api";
import { ErrorState, Loading } from "@/components/ui";

type Lesson = {
  id: string; title: string; summary: string; content_md: string; learning_outcome: string; estimated_minutes: number;
  course_slug: string; course_title: string; status: "not_started" | "in_progress" | "completed";
  exercises: { id: string; title: string; objective: string; authorised_environment: string; expected_result: string;
    safety_restrictions: string; instructions_md: string; lab_slug: string | null }[];
  quiz: { id: string; title: string; pass_mark: number; questions: { id: string; prompt: string; options: string[] }[] } | null;
};
type QuizResult = { correct_count: number; total_count: number; score_pct: string | number; pass_mark: number; passed: boolean;
  results: { question_id: string; correct_option: number; is_correct: boolean; explanation: string }[] };

export default function LessonPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: lesson, error, mutate } = useApi<Lesson>(`academy/lessons/${encodeURIComponent(id)}`);
  const [completing, setCompleting] = useState(false);

  // Record that the learner opened the lesson (counts toward progress and streaks).
  useEffect(() => {
    if (lesson && lesson.status === "not_started") apiSend(`academy/lessons/${lesson.id}/start`, "POST").then(() => mutate());
  }, [lesson, mutate]);

  if (error) return <ErrorState message={error.status === 404 || error.status === 422 ? "This lesson does not exist." : error.message} />;
  if (!lesson) return <Loading label="Loading lesson" />;

  async function complete() {
    setCompleting(true);
    await apiSend(`academy/lessons/${lesson!.id}/complete`, "POST");
    await mutate();
    setCompleting(false);
  }

  return (
    <article className="mx-auto max-w-3xl">
      <Link href={`/academy/${lesson.course_slug}`} className="link">{lesson.course_title}</Link>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight">{lesson.title}</h1>
      <p className="mt-1 text-muted">{lesson.summary} · about {lesson.estimated_minutes} minutes</p>
      <div className="mt-5 rounded-xl border border-cyan/30 bg-cyan/5 p-4 text-sm">
        <b className="font-semibold">By the end you will be able to: </b>{lesson.learning_outcome}
      </div>

      <div className="prose-lesson mt-4">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{lesson.content_md}</ReactMarkdown>
      </div>

      {lesson.exercises.map((ex) => <Exercise key={ex.id} exercise={ex} />)}
      {lesson.quiz && <Quiz quiz={lesson.quiz} />}

      <div className="mt-10 flex flex-wrap items-center gap-3 border-t border-line-soft pt-6">
        {lesson.status === "completed" ? (
          <p className="inline-flex items-center gap-2 text-cyan"><CheckCircle2 size={18} aria-hidden /> Lesson completed</p>
        ) : (
          <button className="btn-primary" onClick={complete} disabled={completing}>{completing ? "Saving…" : "Mark lesson as complete"}</button>
        )}
        <Link href={`/academy/${lesson.course_slug}`} className="btn-ghost">Back to course</Link>
      </div>
    </article>
  );
}

function Exercise({ exercise }: { exercise: Lesson["exercises"][number] }) {
  type Lab = { answer_fields: { name: string; label: string }[] };
  type Graded = { score: number; max_score: number; is_correct: boolean; feedback: { field: string; is_correct: boolean }[]; explanation: string | null };
  const lab = useApi<Lab>(exercise.lab_slug ? `labs/${exercise.lab_slug}` : null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Graded | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try { setResult(await apiSend<Graded>(`labs/${exercise.lab_slug}/submit`, "POST", { answers })); }
    catch (x) { setErr(x instanceof ApiError ? x.message : "Could not check your answer."); }
    finally { setBusy(false); }
  }

  return (
    <section className="panel mt-8" aria-labelledby={`ex-${exercise.id}`}>
      <span className="sim-badge">Practical exercise · simulated data</span>
      <h2 id={`ex-${exercise.id}`} className="mt-2 text-xl font-semibold">{exercise.title}</h2>
      <dl className="mt-3 grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[170px_1fr]">
        <dt className="text-faint">Objective</dt><dd>{exercise.objective}</dd>
        <dt className="text-faint">Authorised environment</dt><dd>{exercise.authorised_environment}</dd>
        <dt className="text-faint">Expected result</dt><dd>{exercise.expected_result}</dd>
        <dt className="text-faint">Safety restrictions</dt><dd>{exercise.safety_restrictions}</dd>
      </dl>
      <div className="prose-lesson mt-2 text-sm"><ReactMarkdown>{exercise.instructions_md}</ReactMarkdown></div>
      {lab.data && (
        <form onSubmit={submit} className="mt-3 flex flex-col gap-3">
          {lab.data.answer_fields.map((f) => {
            const fb = result?.feedback.find((x) => x.field === f.name);
            return (
              <div key={f.name}>
                <label htmlFor={`${exercise.id}-${f.name}`} className="label">{f.label}</label>
                <div className="flex items-center gap-2">
                  <input id={`${exercise.id}-${f.name}`} className="input font-mono" required maxLength={120}
                         value={answers[f.name] ?? ""} onChange={(e) => setAnswers({ ...answers, [f.name]: e.target.value })} />
                  {fb && (fb.is_correct ? <CheckCircle2 className="shrink-0 text-cyan" aria-label="Correct" />
                                        : <XCircle className="shrink-0 text-sev-critical" aria-label="Not correct yet" />)}
                </div>
              </div>
            );
          })}
          <button className="btn-primary self-start" disabled={busy}>{busy ? "Checking…" : "Check my answer"}</button>
        </form>
      )}
      {err && <div className="mt-3"><ErrorState message={err} /></div>}
      {result && (
        <div role="status" className={`mt-3 rounded-lg p-3 text-sm ${result.is_correct ? "bg-cyan/10" : "bg-sev-medium/10"}`}>
          <b>{result.is_correct ? "Correct." : `Not quite: ${result.score}/${result.max_score}.`}</b>{" "}
          {result.is_correct ? result.explanation : "Fields marked with a cross need another look. Use the lab data to check."}
        </div>
      )}
    </section>
  );
}

function Quiz({ quiz }: { quiz: NonNullable<Lesson["quiz"]> }) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [result, setResult] = useState<QuizResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const allAnswered = quiz.questions.every((q) => answers[q.id] !== undefined);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try { setResult(await apiSend<QuizResult>(`academy/quizzes/${quiz.id}/submit`, "POST", { answers })); }
    catch (x) { setErr(x instanceof ApiError ? x.message : "Could not submit the quiz."); }
    finally { setBusy(false); }
  }

  return (
    <section className="panel mt-8" aria-labelledby="quiz-title">
      <h2 id="quiz-title" className="text-xl font-semibold">{quiz.title}</h2>
      <p className="text-sm text-muted">Pass mark {quiz.pass_mark}%. You can retake it as often as you like.</p>
      <form onSubmit={submit} className="mt-4 flex flex-col gap-6">
        {quiz.questions.map((q, qi) => {
          const r = result?.results.find((x) => x.question_id === q.id);
          return (
            <fieldset key={q.id}>
              <legend className="mb-2 font-medium">{qi + 1}. {q.prompt}</legend>
              <div className="flex flex-col gap-1.5">
                {q.options.map((opt, oi) => {
                  const chosen = answers[q.id] === oi;
                  const tone = r ? (oi === r.correct_option ? "border-cyan bg-cyan/10" : chosen ? "border-sev-critical bg-sev-critical/10" : "border-line-soft")
                                 : chosen ? "border-electric bg-electric/10" : "border-line-soft";
                  return (
                    <label key={oi} className={`flex cursor-pointer items-start gap-2.5 rounded-lg border px-3 py-2 text-sm ${tone}`}>
                      <input type="radio" name={q.id} checked={chosen} disabled={!!result} className="mt-1 accent-[#3d7bff]"
                             onChange={() => setAnswers({ ...answers, [q.id]: oi })} />
                      {opt}
                    </label>
                  );
                })}
              </div>
              {r && <p className={`mt-2 text-sm ${r.is_correct ? "text-cyan" : "text-sev-medium"}`}>{r.is_correct ? "Correct. " : "Not this time. "}<span className="text-muted">{r.explanation}</span></p>}
            </fieldset>
          );
        })}
        {err && <ErrorState message={err} />}
        {!result ? (
          <button className="btn-primary self-start" disabled={!allAnswered || busy}>{busy ? "Marking…" : "Submit answers"}</button>
        ) : (
          <div role="status" className="flex flex-wrap items-center gap-3">
            <b className={result.passed ? "text-cyan" : "text-sev-medium"}>
              {result.correct_count}/{result.total_count} correct ({Math.round(Number(result.score_pct))}%) — {result.passed ? "passed" : "not passed yet"}
            </b>
            <button type="button" className="btn-ghost" onClick={() => { setResult(null); setAnswers({}); }}>Try again</button>
          </div>
        )}
      </form>
    </section>
  );
}
