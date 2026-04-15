"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, getToken } from "@/lib/api";
import { ThreadPostCard, ThreadPostOut as ThreadOut } from "@/components/ThreadPostCard";

type Compare = {
  match_percent: number;
  base_match_percent?: number | null;
  weighted_active?: boolean;
  soft_penalty_notes?: string[];
  agreements: { axis: string; slug: string; detail: string }[];
  differences: { axis: string; slug: string; detail: string }[];
  their_mind_lines?: string[];
  your_mind_lines?: string[];
  match_headline?: string;
  shared_traits?: {
    axis: string;
    slug: string;
    summary: string;
    strength?: string;
    detail?: string;
  }[];
  conversation_prompts?: {
    axis: string;
    slug: string;
    prompt: string;
    note?: string;
    detail?: string;
  }[];
  dealbreaker_hit?: boolean;
};

type UserPublic = {
  id: number;
  display_name: string;
  avatar_url?: string | null;
  about_me?: string | null;
  identity_verified?: boolean;
  answers_hidden_from_others?: boolean;
};

function initialsFrom(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function publicImgSrc(url: string | null | undefined): string {
  const u = (url || "").trim();
  if (!u) return "";
  if (u.startsWith("http://") || u.startsWith("https://")) return u;
  if (u.startsWith("/api/")) return u;
  if (u.startsWith("/")) return `/api${u}`;
  return u;
}

function Avatar({ name, url }: { name: string; url?: string | null }) {
  const initials = initialsFrom(name);
  // eslint-disable-next-line @next/next/no-img-element
  return url ? (
    <img
      src={publicImgSrc(url)}
      alt={`Аватар ${name}`}
      className="h-16 w-16 rounded-full object-cover border border-emerald-500/20 ring-2 ring-black/20 shadow-lg shadow-black/30"
    />
  ) : (
    <div className="h-16 w-16 rounded-full border border-emerald-500/20 ring-2 ring-black/20 bg-gradient-to-br from-emerald-900/70 to-zinc-900 flex items-center justify-center shadow-lg shadow-black/30">
      <span className="text-base font-semibold text-emerald-100/90">{initials}</span>
    </div>
  );
}

function parseMindLine(line: string): { axis: string; position: string } | null {
  const s = (line || "").trim();
  if (!s) return null;
  // Typical format: «Axis»: скорее ... .
  const m = s.match(/[«"](.*?)[»"]\s*:\s*(.+)$/);
  if (m && m[1] && m[2]) {
    return { axis: m[1].trim(), position: m[2].trim() };
  }
  // Fallback: split by first colon
  const idx = s.indexOf(":");
  if (idx > 0) {
    return { axis: s.slice(0, idx).replace(/[«»"]/g, "").trim(), position: s.slice(idx + 1).trim() };
  }
  return { axis: "Ось", position: s };
}

export default function UserComparePage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);
  const [userInfo, setUserInfo] = useState<UserPublic | null>(null);
  const [data, setData] = useState<Compare | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reportOpen, setReportOpen] = useState(false);
  const [reportReason, setReportReason] = useState("");
  const [modBusy, setModBusy] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [activityTab, setActivityTab] = useState<"posts" | "replies">("posts");
  const [activity, setActivity] = useState<ThreadOut[]>([]);
  const [activityNext, setActivityNext] = useState<string | null>(null);
  const [activityLoading, setActivityLoading] = useState(false);
  // meId isn't used beyond the self-redirect check, keep only setter-less local state.

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    if (!Number.isFinite(id)) return;
    (async () => {
      try {
        const me = await api<{ id: number }>("/auth/me");
        if (me.id === id) {
          router.replace("/summary");
          return;
        }
        const [u, c] = await Promise.all([api<UserPublic>(`/users/${id}`), api<Compare>(`/users/${id}/compare`)]);
        setUserInfo(u);
        setData(c);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Ошибка");
      }
    })();
  }, [id, router]);

  async function loadActivity(first = false) {
    if (!Number.isFinite(id)) return;
    setActivityLoading(true);
    try {
      const cursor = first ? null : activityNext;
      const qs = new URLSearchParams();
      qs.set("kind", activityTab);
      qs.set("limit", "12");
      if (cursor) qs.set("cursor", cursor);
      const out = await api<{ items: ThreadOut[]; next_cursor: string | null }>(`/users/${id}/threads?${qs.toString()}`);
      if (first) {
        setActivity(out.items);
      } else {
        setActivity((prev) => [...prev, ...out.items]);
      }
      setActivityNext(out.next_cursor);
    } catch {
      // keep main page usable even if activity fails
    } finally {
      setActivityLoading(false);
    }
  }

  useEffect(() => {
    setActivity([]);
    setActivityNext(null);
    void loadActivity(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, activityTab]);

  async function onLike() {
    setMsg(null);
    try {
      const res = await api<{ mutual: boolean; match_id: number | null; conversation_id: number | null }>("/likes", {
        method: "POST",
        body: JSON.stringify({ to_user_id: id }),
      });
      if (res.mutual && res.match_id) {
        setConversationId(res.conversation_id ?? null);
        setMsg("Взаимно! Можно сразу перейти в чат.");
      } else {
        setMsg("Лайк отправлен. Если ответят взаимностью — появится матч.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function onBlock() {
    if (!confirm("Заблокировать пользователя? Вы перестанете видеть друг друга в ленте и чатах.")) return;
    setModBusy(true);
    setError(null);
    try {
      await api(`/users/${id}/block`, { method: "POST" });
      router.replace("/feed");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setModBusy(false);
    }
  }

  async function onSubmitReport() {
    if (!reportReason.trim()) return;
    setModBusy(true);
    setError(null);
    try {
      await api(`/users/${id}/report`, {
        method: "POST",
        body: JSON.stringify({ reason: reportReason.trim() }),
      });
      setReportOpen(false);
      setReportReason("");
      setMsg("Жалоба отправлена. Спасибо.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setModBusy(false);
    }
  }

  if (error && !data) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-zinc-950 text-red-400 px-6">
        {error}
      </main>
    );
  }

  if (!data) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-zinc-950 text-zinc-400">
        Загрузка…
      </main>
    );
  }

  return (
    <main className="mm-page scrollbar-thin">
      <Link href="/feed" className="text-sm text-zinc-500 hover:text-zinc-300">
        ← Назад
      </Link>

      <section className="mt-5 mm-card-static">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold text-zinc-50">
              {userInfo?.display_name ? userInfo.display_name : "Пользователь"}
            </h1>
            <p className="text-sm text-zinc-500 mt-1">Совпадение по ценностям</p>
            <p className="text-4xl font-bold text-emerald-400 mt-2">{data.match_percent}%</p>
            {data.weighted_active && data.base_match_percent != null ? (
              <p className="text-xs text-zinc-500 mt-2">
                Без весов из настроек ленты было бы ~{data.base_match_percent}%
              </p>
            ) : null}
          </div>

          <div className="shrink-0 flex flex-col items-end gap-2">
            <Avatar name={userInfo?.display_name || "Пользователь"} url={userInfo?.avatar_url} />
            {userInfo?.identity_verified ? (
              <span className="mm-badge-accent">✓ фото загружено</span>
            ) : (
              <span className="mm-badge">без фото</span>
            )}
          </div>
        </div>

        {data.dealbreaker_hit ? (
          <p className="mt-3 text-sm text-red-400/90">
            Сработал dealbreaker: по выбранной вами оси слишком большое расхождение — процент сильно ограничен.
          </p>
        ) : null}

        {(data.soft_penalty_notes ?? []).length ? (
          <ul className="mt-3 text-xs text-amber-500/90 space-y-0.5">
            {(data.soft_penalty_notes ?? []).map((n) => (
              <li key={n}>⚠ {n}</li>
            ))}
          </ul>
        ) : null}

        {data.match_headline ? (
          <p className="mt-4 text-sm text-zinc-300 leading-relaxed border-l-2 border-emerald-500/40 pl-3">
            {data.match_headline}
          </p>
        ) : null}

        {userInfo?.answers_hidden_from_others ? (
          <p className="text-xs text-zinc-500 mt-4 max-w-prose">
            Ответы на вопросы теста скрыты; вы видите только сводку по осям и совпадение — так честнее отвечать
            всем.
          </p>
        ) : null}
      </section>

      {/* moved into the profile header card above */}

      {userInfo?.about_me ? (
        <section className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
          <p className="text-xs uppercase tracking-wide text-zinc-500 mb-2">О человеке</p>
          <p className="text-sm text-zinc-300 whitespace-pre-wrap">{userInfo.about_me}</p>
        </section>
      ) : null}

      {(data.their_mind_lines ?? []).length ? (
        <section className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
          <p className="text-xs uppercase tracking-wide text-zinc-500 mb-2">Как этот человек думает</p>
          <div className="flex flex-wrap gap-2">
            {(data.their_mind_lines ?? [])
              .map((line) => ({ raw: line, p: parseMindLine(line) }))
              .filter((x) => x.p)
              .map(({ raw, p }) => (
                <span
                  key={raw}
                  className="inline-flex items-center gap-2 rounded-full border border-zinc-700/80 bg-zinc-950/30 px-3 py-1 text-xs text-zinc-300"
                  title={raw}
                >
                  <span className="text-zinc-400">{p!.axis}</span>
                  <span className="text-zinc-600">·</span>
                  <span className="text-emerald-200/90">{p!.position}</span>
                </span>
              ))}
          </div>
        </section>
      ) : null}

      {/* NOTE: "У вас для сравнения" intentionally hidden per product decision. */}

      <section className="mt-8">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm uppercase tracking-wide text-zinc-500">Активность</h2>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setActivityTab("posts")}
              className={`rounded-full px-3 py-1 text-xs border ${
                activityTab === "posts"
                  ? "border-emerald-500/45 bg-emerald-500/10 text-emerald-200"
                  : "border-zinc-700 text-zinc-400"
              }`}
            >
              Посты
            </button>
            <button
              type="button"
              onClick={() => setActivityTab("replies")}
              className={`rounded-full px-3 py-1 text-xs border ${
                activityTab === "replies"
                  ? "border-emerald-500/45 bg-emerald-500/10 text-emerald-200"
                  : "border-zinc-700 text-zinc-400"
              }`}
            >
              Комментарии
            </button>
          </div>
        </div>

        <ul className="mt-4 space-y-3">
          {activity.map((p) => (
            <li key={p.id}>
              <ThreadPostCard post={p} compact />
            </li>
          ))}
        </ul>

        {!activity.length && !activityLoading ? (
          <p className="mm-empty mt-3">
            {activityTab === "posts" ? "Пока нет постов в ленте." : "Пока нет комментариев."}
          </p>
        ) : null}

        {activityNext ? (
          <button
            type="button"
            disabled={activityLoading}
            className="mt-4 mm-btn-secondary w-full py-3"
            onClick={() => void loadActivity(false)}
          >
            {activityLoading ? "…" : "Показать ещё"}
          </button>
        ) : null}
      </section>

      <section className="mt-8">
        <details className="rounded-2xl border border-zinc-800 bg-zinc-900/25 p-4">
          <summary className="cursor-pointer select-none text-sm font-medium text-zinc-200">
            Показать детали по осям
          </summary>
          <div className="mt-4 space-y-8">
            {(data.shared_traits ?? []).length ? (
              <section>
                <h2 className="text-sm uppercase tracking-wide text-emerald-500 mb-3">Общие черты</h2>
                <ul className="space-y-2">
                  {(data.shared_traits ?? []).map((t) => (
                    <li
                      key={t.slug + t.summary}
                      className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 px-3 py-2 text-sm space-y-1"
                    >
                      <p className="font-medium text-emerald-200/90">{t.axis}</p>
                      <p className="text-zinc-300 text-xs leading-relaxed">{t.summary}</p>
                      {t.strength === "high" ? (
                        <span className="text-[10px] uppercase tracking-wide text-emerald-500/80">сильное сходство</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            <section>
              <h2 className="text-sm uppercase tracking-wide text-emerald-500/60 mb-3">Кратко по осям</h2>
              <ul className="space-y-2">
                {data.agreements.map((x) => (
                  <li
                    key={x.slug + x.detail}
                    className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 px-3 py-2 text-sm"
                  >
                    {x.detail}
                  </li>
                ))}
                {!data.agreements.length && <li className="text-zinc-500 text-sm">Пока нет явных совпадений по осям.</li>}
              </ul>
            </section>

            {(data.conversation_prompts ?? []).length ? (
              <section>
                <h2 className="text-sm uppercase tracking-wide text-sky-500 mb-3">Повод для разговора</h2>
                <ul className="space-y-3">
                  {(data.conversation_prompts ?? []).map((p) => (
                    <li
                      key={p.slug + p.prompt}
                      className="rounded-lg bg-sky-500/10 border border-sky-500/30 px-3 py-3 text-sm"
                    >
                      <p className="text-xs text-sky-500/80 mb-1">{p.axis}</p>
                      <p className="text-zinc-200 leading-relaxed">{p.prompt}</p>
                      {p.note ? <p className="text-xs text-zinc-500 mt-2">{p.note}</p> : null}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            <section>
              <h2 className="text-sm uppercase tracking-wide text-amber-500 mb-3">Сильные различия</h2>
              <ul className="space-y-2">
                {data.differences.map((x) => (
                  <li
                    key={x.slug + x.detail}
                    className="rounded-lg bg-amber-500/10 border border-amber-500/30 px-3 py-2 text-sm"
                  >
                    {x.detail}
                  </li>
                ))}
                {!data.differences.length && <li className="text-zinc-500 text-sm">Сильных расхождений не видно.</li>}
              </ul>
            </section>
          </div>
        </details>
      </section>

      {msg && <p className="mt-6 text-sm text-emerald-400">{msg}</p>}
      {error && <p className="mt-2 text-sm text-red-400">{error}</p>}

      <div className="mt-10 flex flex-col gap-3">
        <button
          type="button"
          onClick={onLike}
          className="rounded-xl bg-emerald-500 text-zinc-950 font-medium py-3 px-4 hover:bg-emerald-400"
        >
          Интересно (лайк)
        </button>
        {conversationId ? (
          <Link
            href={`/chat/${conversationId}`}
            className="rounded-xl border border-emerald-500/50 bg-emerald-500/10 text-center py-3 px-4 text-sm text-emerald-300 hover:border-emerald-400"
          >
            Начать чат
          </Link>
        ) : null}
        <p className="text-xs text-zinc-600">
          После взаимного лайка открой раздел «Диалоги» — там появится личный чат.
        </p>
        <div className="flex flex-wrap gap-2 pt-2 border-t border-zinc-800">
          <button
            type="button"
            disabled={modBusy}
            onClick={() => setReportOpen(true)}
            className="text-sm text-amber-500/90 hover:text-amber-400 underline disabled:opacity-50"
          >
            Пожаловаться
          </button>
          <button
            type="button"
            disabled={modBusy}
            onClick={() => void onBlock()}
            className="text-sm text-zinc-500 hover:text-red-400 underline disabled:opacity-50"
          >
            Заблокировать
          </button>
        </div>
      </div>

      {reportOpen && (
        <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900/60 p-4 space-y-3">
          <p className="text-sm text-zinc-400">Кратко опишите проблему (для модерации).</p>
          <textarea
            className="w-full rounded-lg bg-zinc-950 border border-zinc-700 px-3 py-2 text-sm min-h-[80px]"
            value={reportReason}
            onChange={(e) => setReportReason(e.target.value)}
            placeholder="Текст жалобы"
          />
          <div className="flex gap-2">
            <button
              type="button"
              disabled={modBusy || !reportReason.trim()}
              onClick={() => void onSubmitReport()}
              className="rounded-lg bg-amber-600/80 px-3 py-1.5 text-sm disabled:opacity-50"
            >
              Отправить
            </button>
            <button
              type="button"
              className="text-sm text-zinc-500"
              onClick={() => {
                setReportOpen(false);
                setReportReason("");
              }}
            >
              Отмена
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
