"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, getToken } from "@/lib/api";

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

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    if (!Number.isFinite(id)) return;
    (async () => {
      try {
        const [u, c] = await Promise.all([
          api<UserPublic>(`/users/${id}`),
          api<Compare>(`/users/${id}/compare`),
        ]);
        setUserInfo(u);
        setData(c);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Ошибка");
      }
    })();
  }, [id, router]);

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
        ← К ленте
      </Link>
      <h1 className="text-2xl font-semibold mt-6">
        {userInfo?.display_name ? userInfo.display_name : "Пользователь"} · сравнение
      </h1>
      {userInfo?.identity_verified ? (
        <p className="text-xs text-sky-400/90 mt-1">✓ Отметка «фото загружено» в профиле</p>
      ) : null}
      {userInfo?.answers_hidden_from_others ? (
        <p className="text-xs text-zinc-500 mt-2 max-w-prose">
          Ответы на вопросы теста скрыты; вы видите только сводку по осям и совпадение — так честнее отвечать
          всем.
        </p>
      ) : null}
      <p className="text-4xl font-bold text-emerald-400 mt-2">{data.match_percent}%</p>
      {data.weighted_active && data.base_match_percent != null ? (
        <p className="text-sm text-zinc-500 mt-1">
          Без весов из настроек ленты было бы ~{data.base_match_percent}%
        </p>
      ) : null}
      {data.dealbreaker_hit ? (
        <p className="mt-2 text-sm text-red-400/90">
          Сработал dealbreaker: по выбранной вами оси слишком большое расхождение — процент сильно
          ограничен.
        </p>
      ) : null}

      {(data.soft_penalty_notes ?? []).length ? (
        <ul className="mt-2 text-xs text-amber-500/90 space-y-0.5">
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

      {userInfo?.about_me ? (
        <section className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
          <p className="text-xs uppercase tracking-wide text-zinc-500 mb-2">О человеке</p>
          <p className="text-sm text-zinc-300 whitespace-pre-wrap">{userInfo.about_me}</p>
        </section>
      ) : null}

      {(data.their_mind_lines ?? []).length ? (
        <section className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900/30 p-4">
          <p className="text-xs uppercase tracking-wide text-zinc-500 mb-2">Как этот человек думает</p>
          <ul className="space-y-1 text-sm text-zinc-300">
            {(data.their_mind_lines ?? []).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {(data.your_mind_lines ?? []).length ? (
        <section className="mt-4 rounded-xl border border-zinc-800/80 bg-zinc-950/40 p-4">
          <p className="text-xs uppercase tracking-wide text-zinc-500 mb-2">У вас для сравнения</p>
          <ul className="space-y-1 text-sm text-zinc-400">
            {(data.your_mind_lines ?? []).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {(data.shared_traits ?? []).length ? (
        <section className="mt-8">
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

      <section className="mt-8">
        <h2 className="text-sm uppercase tracking-wide text-emerald-500/60 mb-3">Кратко по осям</h2>
        <ul className="space-y-2">
          {data.agreements.map((x) => (
            <li key={x.slug + x.detail} className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 px-3 py-2 text-sm">
              {x.detail}
            </li>
          ))}
          {!data.agreements.length && (
            <li className="text-zinc-500 text-sm">Пока нет явных совпадений по осям.</li>
          )}
        </ul>
      </section>

      {(data.conversation_prompts ?? []).length ? (
        <section className="mt-8">
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

      <section className="mt-8">
        <h2 className="text-sm uppercase tracking-wide text-amber-500 mb-3">Сильные различия</h2>
        <ul className="space-y-2">
          {data.differences.map((x) => (
            <li key={x.slug + x.detail} className="rounded-lg bg-amber-500/10 border border-amber-500/30 px-3 py-2 text-sm">
              {x.detail}
            </li>
          ))}
          {!data.differences.length && (
            <li className="text-zinc-500 text-sm">Сильных расхождений не видно.</li>
          )}
        </ul>
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
