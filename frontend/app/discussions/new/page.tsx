"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { api, getToken } from "@/lib/api";

type AxisOpt = { slug: string; name: string };

export default function NewDiscussionPage() {
  const router = useRouter();
  const [axes, setAxes] = useState<AxisOpt[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const [me, a] = await Promise.all([
          api<{ onboarding_step: string }>("/auth/me"),
          api<AxisOpt[]>("/discussions/axes"),
        ]);
        if (me.onboarding_step !== "test_completed") {
          router.replace("/test");
          return;
        }
        if (!cancelled) setAxes(a);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Ошибка");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  function toggle(slug: string) {
    setPicked((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]
    );
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!title.trim() || !body.trim() || !picked.length) {
      setError("Нужны заголовок, текст и хотя бы одна тема (ось).");
      return;
    }
    setBusy(true);
    try {
      const created = await api<{ id: number }>("/discussions/posts", {
        method: "POST",
        body: JSON.stringify({
          title: title.trim(),
          body: body.trim(),
          theme_axis_slugs: picked,
        }),
      });
      router.replace(`/discussions/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mm-page scrollbar-thin">
      <Link href="/discussions" className="text-sm text-zinc-500 hover:text-emerald-400/90 transition-colors">
        ← Назад
      </Link>
      <h1 className="mm-h2 mt-4">Новый пост</h1>
      <p className="mm-lead mt-2">
        Выберите темы (оси из теста), затем текст. Обложку можно добавить на странице поста после публикации.
      </p>

      <form onSubmit={onSubmit} className="mt-8 space-y-5">
        <label className="mm-label">
          <span>Заголовок</span>
          <input className="mm-input" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={220} />
        </label>
        <label className="mm-label">
          <span>Текст</span>
          <textarea
            className="mm-input min-h-[140px]"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            maxLength={8000}
          />
        </label>
        <div>
          <p className="text-xs text-zinc-500 mb-2">Темы (оси)</p>
          <div className="flex flex-wrap gap-2">
            {axes.map((a) => (
              <button
                key={a.slug}
                type="button"
                onClick={() => toggle(a.slug)}
                className={`rounded-full px-3 py-1 text-xs border ${
                  picked.includes(a.slug)
                    ? "border-emerald-500/60 bg-emerald-500/10 text-emerald-200"
                    : "border-zinc-700 text-zinc-400"
                }`}
              >
                {a.name}
              </button>
            ))}
          </div>
        </div>
        {error ? <p className="mm-error">{error}</p> : null}
        <button type="submit" disabled={busy} className="mm-btn-primary w-full py-3.5">
          {busy ? "…" : "Опубликовать"}
        </button>
      </form>

      <BottomNav />
    </main>
  );
}
