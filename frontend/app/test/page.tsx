"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api, getToken } from "@/lib/api";

type Question = {
  id: number;
  pack: string;
  qtype: string;
  text: string;
  order_index: number;
  option_a: string | null;
  option_b: string | null;
  likert_min: number;
  likert_max: number;
  likert_left_label?: string | null;
  likert_right_label?: string | null;
  likert_bipolar_invert?: boolean;
  likert_scale_hints?: string[] | null;
  axes: { slug: string; name: string }[];
};

type AnswerDraft = {
  question_id: number;
  value_numeric?: number;
  value_choice?: string;
};

function isBipolarLikert(q: Question): boolean {
  return Boolean(q.likert_left_label && q.likert_right_label);
}

/** Позиция ползунка (слева = min, справа = max) → значение для API. */
function sliderToStored(q: Question, sliderPos: number): number {
  if (!isBipolarLikert(q)) return sliderPos;
  if (q.likert_bipolar_invert) {
    return q.likert_min + q.likert_max - sliderPos;
  }
  return sliderPos;
}

/** API value → позиция ползунка. */
function storedToSlider(q: Question, stored: number): number {
  if (!isBipolarLikert(q)) return stored;
  if (q.likert_bipolar_invert) {
    return q.likert_min + q.likert_max - stored;
  }
  return stored;
}

function neutralSlider(q: Question): number {
  return Math.round((q.likert_min + q.likert_max) / 2);
}

function bipolarHint(q: Question, sliderPos: number): string {
  const mid = (q.likert_min + q.likert_max) / 2;
  const dist = Math.abs(sliderPos - mid);
  if (dist < 0.51) {
    return "По центру — нейтрально, без явного выбора стороны.";
  }
  if (sliderPos < mid) {
    return `Ближе к «${q.likert_left_label}»`;
  }
  return `Ближе к «${q.likert_right_label}»`;
}

/** Подпись под ползунком: по шагам с бэка (по value_numeric) или общая биполярная. */
function likertHintCaption(q: Question, stored: number): string {
  const hints = q.likert_scale_hints;
  const span = q.likert_max - q.likert_min + 1;
  if (hints && hints.length === span) {
    const i = stored - q.likert_min;
    if (i >= 0 && i < hints.length) return hints[i];
  }
  return bipolarHint(q, storedToSlider(q, stored));
}

function isNeutralTickStep(q: Question, step: number): boolean {
  const mid = (q.likert_min + q.likert_max) / 2;
  return Math.abs(step - mid) <= 0.51;
}

function likertSteps(q: Question): number[] {
  const out: number[] = [];
  for (let s = q.likert_min; s <= q.likert_max; s++) out.push(s);
  return out;
}

export default function TestPage() {
  const router = useRouter();
  const [questions, setQuestions] = useState<Question[]>([]);
  const [idx, setIdx] = useState(0);
  const [drafts, setDrafts] = useState<Record<number, AnswerDraft>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const q = questions[idx];
  const progress = useMemo(
    () => (questions.length ? Math.round(((idx + 1) / questions.length) * 100) : 0),
    [idx, questions.length]
  );

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const me = await api<{ onboarding_step: string }>("/auth/me");
        if (cancelled) return;
        if (me.onboarding_step === "test_completed") {
          router.replace("/feed");
          return;
        }
        const data = await api<Question[]>("/questions?pack=onboarding");
        if (cancelled) return;
        setQuestions(data.sort((a, b) => a.order_index - b.order_index || a.id - b.id));
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Не удалось загрузить вопросы");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  useEffect(() => {
    if (!q || q.qtype !== "likert") return;
    if (drafts[q.id]?.value_numeric != null) return;
    const mid = neutralSlider(q);
    const stored = sliderToStored(q, mid);
    setDrafts((d) => ({
      ...d,
      [q.id]: { question_id: q.id, value_numeric: stored },
    }));
  }, [q, drafts]);

  function setCurrentAnswer(patch: Partial<AnswerDraft>) {
    if (!q) return;
    setDrafts((d) => ({
      ...d,
      [q.id]: { ...d[q.id], question_id: q.id, ...patch },
    }));
  }

  async function finish() {
    const answers = Object.values(drafts);
    if (answers.length < questions.length) {
      setError("Ответь на все вопросы");
      return;
    }
    setError(null);
    try {
      await api("/answers", {
        method: "POST",
        body: JSON.stringify({ answers }),
      });
      router.push("/summary");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения");
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-zinc-950 text-zinc-400">
        Загрузка…
      </main>
    );
  }

  if (!questions.length) {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center px-6 bg-zinc-950 text-zinc-100 gap-4">
        <p className="text-center text-zinc-400">
          Нет вопросов. Запусти миграции и сид: см. README в корне репозитория.
        </p>
        <Link href="/" className="text-emerald-400 underline">
          На главную
        </Link>
      </main>
    );
  }

  const current = drafts[q.id];
  const canNext =
    q.qtype === "likert"
      ? current?.value_numeric != null
      : Boolean(current?.value_choice);

  const sliderPos =
    q.qtype === "likert" && current?.value_numeric != null
      ? storedToSlider(q, current.value_numeric)
      : q.likert_min;

  const storedNumeric =
    q.qtype === "likert" && current?.value_numeric != null
      ? current.value_numeric
      : sliderToStored(q, neutralSlider(q));

  return (
    <main className="mm-page flex flex-col scrollbar-thin">
      <div className="h-1 w-full bg-zinc-800 rounded overflow-hidden mb-6">
        <div
          className="h-full bg-emerald-500 transition-all"
          style={{ width: `${progress}%` }}
        />
      </div>
      <p className="text-xs text-zinc-500 mb-2">
        {idx + 1} / {questions.length}
      </p>
      <h1 className="text-lg font-medium leading-snug">{q.text}</h1>

      {q.qtype === "likert" && isBipolarLikert(q) && (
        <div className="mt-8">
          <div className="flex justify-between gap-3 text-xs text-zinc-400 leading-tight mb-2">
            <span className="text-left max-w-[42%] text-emerald-400/90">{q.likert_left_label}</span>
            <span className="text-right max-w-[42%] text-sky-400/90">{q.likert_right_label}</span>
          </div>
          <div className="relative pt-1">
            <div
              className="pointer-events-none absolute left-0 right-0 top-0 h-5"
              aria-hidden
            >
              {likertSteps(q).map((step) => {
                const i = step - q.likert_min;
                const n = q.likert_max - q.likert_min + 1;
                const pct = n <= 1 ? 50 : (i / (n - 1)) * 100;
                const active = step === sliderPos;
                return (
                  <div
                    key={step}
                    className="absolute top-0 flex -translate-x-1/2 flex-col items-center gap-0.5"
                    style={{ left: `${pct}%` }}
                  >
                    <div
                      className={`w-0.5 rounded-full transition-colors ${
                        active ? "h-3 bg-emerald-400" : "h-2 bg-zinc-600"
                      }`}
                    />
                    {isNeutralTickStep(q, step) && (
                      <span className="whitespace-nowrap text-[9px] leading-none text-zinc-500">
                        нейтр.
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
            <input
              type="range"
              min={q.likert_min}
              max={q.likert_max}
              step={1}
              value={sliderPos}
              onChange={(e) => {
                const pos = Number(e.target.value);
                setCurrentAnswer({ value_numeric: sliderToStored(q, pos) });
              }}
              className="relative z-10 w-full accent-emerald-500 h-3"
            />
          </div>
          <p className="mt-6 text-sm text-zinc-300 text-center min-h-[2.5rem] px-1 leading-snug">
            {likertHintCaption(q, storedNumeric)}
          </p>
        </div>
      )}

      {q.qtype === "likert" && !isBipolarLikert(q) && (
        <div className="mt-8">
          <label className="flex flex-col gap-2 text-sm text-zinc-400">
            Шкала {q.likert_min}–{q.likert_max}
            <input
              type="range"
              min={q.likert_min}
              max={q.likert_max}
              value={current?.value_numeric ?? q.likert_min}
              onChange={(e) =>
                setCurrentAnswer({ value_numeric: Number(e.target.value) })
              }
              className="w-full accent-emerald-500"
            />
          </label>
          <p className="mt-4 text-3xl font-semibold text-emerald-400 text-center">
            {current?.value_numeric ?? q.likert_min}
          </p>
        </div>
      )}

      {(q.qtype === "binary" || q.qtype === "forced_choice") && (
        <div className="mt-8 flex flex-col gap-3">
          <button
            type="button"
            onClick={() => setCurrentAnswer({ value_choice: "a" })}
            className={`rounded-xl border py-3 px-4 text-left transition ${
              current?.value_choice === "a"
                ? "border-emerald-500 bg-emerald-500/10"
                : "border-zinc-700 hover:border-zinc-500"
            }`}
          >
            {q.option_a ?? "A"}
          </button>
          <button
            type="button"
            onClick={() => setCurrentAnswer({ value_choice: "b" })}
            className={`rounded-xl border py-3 px-4 text-left transition ${
              current?.value_choice === "b"
                ? "border-emerald-500 bg-emerald-500/10"
                : "border-zinc-700 hover:border-zinc-500"
            }`}
          >
            {q.option_b ?? "B"}
          </button>
        </div>
      )}

      {error && <p className="mt-6 text-red-400 text-sm">{error}</p>}

      <div className="mt-auto pt-10 flex gap-3">
        {idx > 0 && (
          <button
            type="button"
            onClick={() => setIdx((i) => i - 1)}
            className="flex-1 rounded-xl border border-zinc-600 py-3"
          >
            Назад
          </button>
        )}
        {idx < questions.length - 1 ? (
          <button
            type="button"
            disabled={!canNext}
            onClick={() => setIdx((i) => i + 1)}
            className="flex-1 rounded-xl bg-emerald-500 text-zinc-950 font-medium py-3 disabled:opacity-40"
          >
            Далее
          </button>
        ) : (
          <button
            type="button"
            disabled={!canNext}
            onClick={finish}
            className="flex-1 rounded-xl bg-emerald-500 text-zinc-950 font-medium py-3 disabled:opacity-40"
          >
            Готово
          </button>
        )}
      </div>
    </main>
  );
}
