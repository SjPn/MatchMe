"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

type AxisOpt = { slug: string; name: string };

export type ThreadPostOut = {
  id: number;
  author: { id: number | null; display_name: string | null };
  parent_id: number | null;
  root_id: number;
  kind: string;
  quote_post_id: number | null;
  quote_preview?: ThreadPostOut | null;
  body: string;
  created_at: string;
  is_system: boolean;
  visibility: string;
  media: { id: number; url: string; mime: string }[];
  reply_count: number;
  like_count: number;
  liked_by_me: boolean;
  repost_count: number;
  quote_count: number;
  topic_axis_slugs: string[];
};

type Mode =
  | { kind: "new" }
  | { kind: "reply"; parent: ThreadPostOut }
  | { kind: "quote"; target: ThreadPostOut };

export function ThreadComposerSheet(props: {
  open: boolean;
  mode: Mode;
  onClose: () => void;
  onCreated?: (post: ThreadPostOut) => void;
}) {
  const { open, mode, onClose, onCreated } = props;
  const [body, setBody] = useState("");
  const [axes, setAxes] = useState<AxisOpt[]>([]);
  const [picked, setPicked] = useState<string[]>([]);
  const [axisMaxDist, setAxisMaxDist] = useState(0.22);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const title = mode.kind === "new" ? "Новый пост" : mode.kind === "reply" ? "Ответ" : "Цитата";
  const quoteStrip = useMemo(() => {
    const src = mode.kind === "reply" ? mode.parent : mode.kind === "quote" ? mode.target : null;
    if (!src) return null;
    const t = src.body.trim().replace(/\s+/g, " ");
    return t.length > 160 ? `${t.slice(0, 159)}…` : t;
  }, [mode]);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setBusy(false);
    if (mode.kind === "new") {
      // Fresh post: fetch axes so user can attach a value contract.
      void (async () => {
        try {
          const a = await api<AxisOpt[]>("/axes");
          setAxes(a);
        } catch {
          setAxes([]);
        }
      })();
    } else {
      setAxes([]);
      setPicked([]);
    }
  }, [open, mode.kind]);

  function toggle(slug: string) {
    setPicked((prev) => (prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    const text = body.trim();
    if (!text) return;
    setBusy(true);
    try {
      let created: ThreadPostOut;
      if (mode.kind === "new") {
        created = await api<ThreadPostOut>("/posts", {
          method: "POST",
          body: JSON.stringify({
            body: text,
            theme_axis_slugs: picked,
            axis_max_dist: axisMaxDist,
          }),
        });
      } else if (mode.kind === "reply") {
        created = await api<ThreadPostOut>(`/posts/${mode.parent.id}/reply`, {
          method: "POST",
          body: JSON.stringify({ body: text }),
        });
      } else {
        created = await api<ThreadPostOut>(`/posts/${mode.target.id}/quote`, {
          method: "POST",
          body: JSON.stringify({ body: text }),
        });
      }
      setBody("");
      setPicked([]);
      onCreated?.(created);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setBusy(false);
    }
  }

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[60]">
      <button
        type="button"
        className="absolute inset-0 bg-zinc-900/35"
        onClick={() => !busy && onClose()}
        aria-label="Закрыть"
      />
      <div className="absolute inset-x-0 bottom-0 mx-auto max-w-shell lg:max-w-shell-wide px-4 sm:px-6 pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <div className="rounded-3xl border border-zinc-200 bg-white shadow-mm-card overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100">
            <p className="text-sm font-semibold text-zinc-900">{title}</p>
            <button
              type="button"
              className="text-zinc-500 hover:text-zinc-800 px-2 py-1 rounded-lg"
              onClick={() => !busy && onClose()}
              aria-label="Закрыть"
            >
              ✕
            </button>
          </div>

          {quoteStrip ? (
            <div className="px-4 pt-3">
              <div className="rounded-2xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-600">
                <span className="text-zinc-500">{mode.kind === "quote" ? "Цитата: " : "В ответ на: "}</span>
                <span className="text-zinc-800">{quoteStrip}</span>
              </div>
            </div>
          ) : null}

          <form onSubmit={onSubmit} className="px-4 py-4 space-y-3">
            <textarea
              className="mm-input min-h-[110px] max-h-[40vh] resize-y"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder={mode.kind === "new" ? "Что у вас нового?" : mode.kind === "quote" ? "Ваш комментарий к цитате…" : "Ваш ответ…"}
              maxLength={mode.kind === "new" ? 8000 : 4000}
              aria-label="Текст"
            />

            {mode.kind === "new" ? (
              <div className="space-y-2">
                <p className="text-xs text-zinc-500">
                  Темы (оси) задают правило ценностей: отвечать смогут люди, чьи позиции по этим осям близки к вашим.
                </p>
                <div className="flex flex-wrap gap-2">
                  {axes.map((a) => (
                    <button
                      key={a.slug}
                      type="button"
                      onClick={() => toggle(a.slug)}
                      className={`rounded-full px-3 py-1 text-xs border ${
                        picked.includes(a.slug)
                          ? "border-sky-500/60 bg-sky-500/10 text-sky-800"
                          : "border-zinc-300 text-zinc-600"
                      }`}
                    >
                      {a.name}
                    </button>
                  ))}
                </div>
                <label className="block">
                  <span className="text-xs text-zinc-500">Строгость (допуск по оси)</span>
                  <input
                    type="range"
                    min={0.05}
                    max={0.45}
                    step={0.01}
                    value={axisMaxDist}
                    onChange={(e) => setAxisMaxDist(Number(e.target.value))}
                    className="w-full accent-sky-500"
                  />
                  <span className="text-[11px] text-zinc-600">±{axisMaxDist.toFixed(2)} вокруг вашей позиции</span>
                </label>
              </div>
            ) : null}

            {error ? <p className="mm-error">{error}</p> : null}

            <div className="flex gap-2">
              <button type="button" className="mm-btn-secondary flex-1" onClick={() => !busy && onClose()}>
                Отмена
              </button>
              <button type="submit" disabled={busy || !body.trim()} className="mm-btn-primary flex-1">
                {busy ? "…" : "Опубликовать"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

