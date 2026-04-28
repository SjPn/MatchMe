"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import {
  isScrollNearBottom,
  playSoftMessagePing,
  requestNotificationPermission,
  showChatNotificationIfAllowed,
} from "@/lib/chatClient";
import { api } from "@/lib/api";

type ReplyPreview = {
  id: number;
  sender_id: number;
  body_snippet: string;
};

type Message = {
  id: number;
  sender_id: number;
  body: string;
  created_at: string;
  reply_to?: ReplyPreview | null;
  sender_display_name?: string | null;
};

type RoomDetail = {
  id: number;
  title: string;
  weekly_theme: string;
  daily_prompt: string;
  shared_traits: string[];
  members: { user_id: number; display_name: string }[];
  community_rules: string[];
  privacy_notice: string;
  platonic_mission?: string;
  cohort_size_note?: string;
  you_muted: boolean;
};

const STICKERS = ["😀", "🔥", "👋", "✨", "💬", "🙌", "🤝", "❤️"];

function mergeById(prev: Message[], incoming: Message[]): Message[] {
  const ids = new Set(prev.map((x) => x.id));
  const add = incoming.filter((x) => !ids.has(x.id));
  return add.length ? [...prev, ...add] : prev;
}

export default function GroupChatPage() {
  const params = useParams();
  const router = useRouter();
  const rid = Number(params.id);
  const [room, setRoom] = useState<RoomDetail | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [meId, setMeId] = useState<number | null>(null);
  const [ready, setReady] = useState(false);
  const [replyTo, setReplyTo] = useState<ReplyPreview | null>(null);
  const [reportFor, setReportFor] = useState<number | null>(null);
  const [reportReason, setReportReason] = useState("");
  const lastIdRef = useRef(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const messagesRef = useRef<Message[]>([]);
  const atBottomRef = useRef(true);
  const lastMarkedReadId = useRef(0);
  const [showNotifyPrompt, setShowNotifyPrompt] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  messagesRef.current = messages;

  function autosizeInput() {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    const cs = window.getComputedStyle(el);
    const lineH = Number.parseFloat(cs.lineHeight || "0") || 20;
    const padTop = Number.parseFloat(cs.paddingTop || "0") || 0;
    const padBottom = Number.parseFloat(cs.paddingBottom || "0") || 0;
    const borderTop = Number.parseFloat(cs.borderTopWidth || "0") || 0;
    const borderBottom = Number.parseFloat(cs.borderBottomWidth || "0") || 0;
    const maxH = lineH * 7 + padTop + padBottom + borderTop + borderBottom;
    const next = Math.min(el.scrollHeight, maxH);
    el.style.height = `${next}px`;
    el.style.overflowY = el.scrollHeight > maxH ? "auto" : "hidden";
  }

  function hideKeyboard() {
    const el = inputRef.current;
    if (!el) return;
    try {
      el.blur();
    } catch {
      /* ignore */
    }
  }

  const tryMarkRead = useCallback(() => {
    if (!ready || !Number.isFinite(rid)) return;
    if (typeof document !== "undefined" && document.hidden) return;
    const box = scrollRef.current;
    if (!box || !isScrollNearBottom(box)) return;
    const list = messagesRef.current;
    const lastId = list.length ? list[list.length - 1].id : 0;
    if (lastId <= 0 || lastId <= lastMarkedReadId.current) return;
    lastMarkedReadId.current = lastId;
    void api(`/group-rooms/${rid}/read?last_message_id=${lastId}`, { method: "POST" });
  }, [ready, rid]);

  useEffect(() => {
    if (!ready) return;
    const box = scrollRef.current;
    if (!box) return;
    if (atBottomRef.current) {
      box.scrollTop = box.scrollHeight;
      tryMarkRead();
    }
  }, [messages, ready, tryMarkRead]);

  useEffect(() => {
    if (!Number.isFinite(rid)) return;
    let cancelled = false;
    (async () => {
      try {
        const [me, detail, all] = await Promise.all([
          api<{ id: number }>("/auth/me"),
          api<RoomDetail>(`/group-rooms/${rid}`),
          api<Message[]>(`/group-rooms/${rid}/messages`),
        ]);
        if (cancelled) return;
        setMeId(me.id);
        setRoom(detail);
        setMessages(all);
        lastIdRef.current = all.length ? all[all.length - 1].id : 0;
        setReady(true);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Ошибка");
        setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [rid]);

  useEffect(() => {
    lastMarkedReadId.current = 0;
    atBottomRef.current = true;
  }, [rid]);

  useEffect(() => {
    if (typeof window !== "undefined" && typeof Notification !== "undefined") {
      setShowNotifyPrompt(Notification.permission === "default");
    }
  }, []);

  useEffect(() => {
    function onVis() {
      if (typeof document !== "undefined" && document.visibilityState === "visible") {
        tryMarkRead();
      }
    }
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [tryMarkRead]);

  useEffect(() => {
    if (!ready || !Number.isFinite(rid)) return;
    function tick() {
      void (async () => {
        try {
          const box = scrollRef.current;
          const wasNearBottom = box ? isScrollNearBottom(box) : true;
          const newer = await api<Message[]>(
            `/group-rooms/${rid}/messages?after_id=${lastIdRef.current}`
          );
          if (newer.length) {
            const me = meId;
            const fromOthers = me != null && newer.some((m) => m.sender_id !== me);
            if (fromOthers && typeof document !== "undefined" && document.hidden) {
              playSoftMessagePing();
              const last = newer[newer.length - 1];
              const snippet = (last.body || "").slice(0, 120) || "Сообщение в группе";
              showChatNotificationIfAllowed(room?.title || "Группа", snippet);
            }
            setMessages((m) => {
              const merged = mergeById(m, newer);
              if (merged !== m) {
                lastIdRef.current = merged[merged.length - 1].id;
              }
              return merged;
            });
            if (wasNearBottom) {
              atBottomRef.current = true;
            } else {
              atBottomRef.current = false;
            }
          }
        } catch {
          /* ignore */
        }
      })();
    }
    const id = window.setInterval(tick, 2500);
    document.addEventListener("visibilitychange", tick);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [ready, rid, meId, room?.title]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    autosizeInput();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [body]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    function onResize() {
      autosizeInput();
    }
    window.addEventListener("resize", onResize);
    window.addEventListener("orientationchange", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("orientationchange", onResize);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!body.trim()) return;
    setError(null);
    try {
      const payload: { body: string; reply_to_message_id?: number } = { body: body.trim() };
      if (replyTo) payload.reply_to_message_id = replyTo.id;
      await api(`/group-rooms/${rid}/messages`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setBody("");
      setReplyTo(null);
      atBottomRef.current = true;
      hideKeyboard();
      if (inputRef.current) {
        inputRef.current.style.height = "auto";
        inputRef.current.style.overflowY = "hidden";
      }
      const newer = await api<Message[]>(`/group-rooms/${rid}/messages?after_id=${lastIdRef.current}`);
      if (newer.length) {
        setMessages((m) => {
          const merged = mergeById(m, newer);
          if (merged !== m) {
            lastIdRef.current = merged[merged.length - 1].id;
          }
          return merged;
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    }
  }

  async function toggleMute() {
    if (!room) return;
    try {
      await api(`/group-rooms/${rid}/mute`, {
        method: "POST",
        body: JSON.stringify({ muted: !room.you_muted }),
      });
      const detail = await api<RoomDetail>(`/group-rooms/${rid}`);
      setRoom(detail);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function leave() {
    if (!confirm("Выйти из группы? Сообщения останутся у других.")) return;
    try {
      await api(`/group-rooms/${rid}/leave`, { method: "POST" });
      router.replace("/conversations");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    }
  }

  async function submitReport() {
    if (!reportFor || !reportReason.trim()) return;
    try {
      await api(`/group-rooms/${rid}/messages/${reportFor}/report`, {
        method: "POST",
        body: JSON.stringify({ reason: reportReason.trim() }),
      });
      setReportFor(null);
      setReportReason("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    }
  }

  if (!ready && !error) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-zinc-950 text-zinc-400">
        Загрузка…
      </main>
    );
  }

  if (error && !room) {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center bg-zinc-950 text-red-400 px-6">
        {error}
        <Link href="/conversations" className="mt-4 text-zinc-500 underline">
          К диалогам
        </Link>
      </main>
    );
  }

  return (
    <main className="mm-page-chat">
      <header className="border-b border-white/[0.06] bg-zinc-950/80 backdrop-blur-md px-4 py-3 shrink-0 space-y-2">
        <div className="flex items-center gap-4">
          <Link href="/conversations" className="text-zinc-500 text-sm">
            ←
          </Link>
          {showNotifyPrompt ? (
            <button
              type="button"
              className="text-[10px] text-sky-500/90 hover:text-sky-400 shrink-0 whitespace-nowrap"
              onClick={() =>
                void (async () => {
                  const p = await requestNotificationPermission();
                  setShowNotifyPrompt(p === "default");
                })()
              }
            >
              Уведомления
            </button>
          ) : null}
          <div className="min-w-0 flex-1">
            <p className="font-medium truncate">{room?.title ?? "Группа"}</p>
            <p className="text-[10px] text-zinc-500">
              Видны только псевдонимы. Почта и данные аккаунта скрыты.
            </p>
          </div>
        </div>
        {room?.platonic_mission ? (
          <p className="text-xs text-zinc-300 border border-zinc-800 rounded-lg px-2 py-1.5 leading-relaxed">
            {room.platonic_mission}
          </p>
        ) : null}
        {room?.cohort_size_note ? (
          <p className="text-[10px] text-zinc-500">{room.cohort_size_note}</p>
        ) : null}
        {room?.weekly_theme ? (
          <p className="text-xs text-zinc-400 border border-zinc-800 rounded-lg px-2 py-1.5">
            <span className="text-zinc-500">Тема недели · </span>
            {room.weekly_theme}
          </p>
        ) : null}
        {room?.daily_prompt ? (
          <p className="text-xs text-emerald-400/90 border border-emerald-500/30 rounded-lg px-2 py-1.5">
            <span className="text-zinc-500">Вопрос дня · </span>
            {room.daily_prompt}
          </p>
        ) : null}
        {room?.shared_traits?.length ? (
          <div className="text-xs text-zinc-400 border border-zinc-800 rounded-lg px-2 py-1.5 space-y-1">
            <span className="text-zinc-500">Общее для вас в этой комнате · </span>
            <ul className="list-disc list-inside space-y-0.5">
              {room.shared_traits.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </div>
        ) : null}
        <div className="flex flex-wrap gap-2 text-[10px]">
          <button
            type="button"
            className="rounded border border-zinc-700 px-2 py-1 text-zinc-400 hover:border-zinc-500"
            onClick={() => void toggleMute()}
          >
            {room?.you_muted ? "Включить уведомления (флаг)" : "Тихий режим"}
          </button>
          <button
            type="button"
            className="rounded border border-zinc-800 px-2 py-1 text-zinc-500 hover:border-red-900/60 hover:text-red-400"
            onClick={() => void leave()}
          >
            Выйти
          </button>
        </div>
      </header>

      {room?.members?.length ? (
        <div className="border-b border-zinc-800 px-4 py-2 text-xs">
          <p className="text-zinc-500 mb-2">Участники</p>
          <div className="flex flex-wrap gap-2">
            {room.members.map((m) => (
              <Link
                key={m.user_id}
                href={`/users/${m.user_id}`}
                className="rounded-full border border-zinc-800 bg-zinc-900/60 px-3 py-1 hover:border-zinc-600 text-zinc-300"
              >
                {m.display_name || `#${m.user_id}`}
              </Link>
            ))}
          </div>
          <p className="text-[10px] text-zinc-600 mt-2">
            Нажмите на ник, чтобы открыть страницу человека и при желании перейти в личный чат (после взаимного лайка).
          </p>
        </div>
      ) : null}

      {room?.community_rules?.length ? (
        <details className="border-b border-zinc-800 px-4 py-2 text-xs text-zinc-500">
          <summary className="cursor-pointer text-zinc-400">Правила сообщества</summary>
          <ul className="mt-2 space-y-1 list-disc pl-4">
            {room.community_rules.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <p className="mt-2 text-zinc-600">{room.privacy_notice}</p>
        </details>
      ) : null}

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-4 space-y-3"
        onPointerDown={() => hideKeyboard()}
        onScroll={() => {
          const box = scrollRef.current;
          if (!box) return;
          atBottomRef.current = isScrollNearBottom(box);
          tryMarkRead();
        }}
      >
        {messages.map((m) => {
          const mine = meId !== null && m.sender_id === meId;
          const label = m.sender_display_name || (mine ? "Вы" : `Участник #${m.sender_id}`);
          return (
            <div
              key={m.id}
              className={`rounded-xl border px-3 py-2 text-sm max-w-[min(100%,24rem)] ${
                mine
                  ? "ml-auto bg-emerald-500/15 border-emerald-500/40"
                  : "mr-auto bg-zinc-900/60 border-zinc-800"
              }`}
            >
              <div className="flex justify-between items-start gap-2 mb-1">
                <p className="text-xs text-zinc-500 truncate">{label}</p>
                <div className="flex gap-1 shrink-0">
                  <button
                    type="button"
                    className="text-[10px] text-zinc-500 hover:text-emerald-400"
                    onClick={() =>
                      setReplyTo({
                        id: m.id,
                        sender_id: m.sender_id,
                        body_snippet: (m.body || "").slice(0, 120),
                      })
                    }
                  >
                    Ответить
                  </button>
                  {!mine ? (
                    <button
                      type="button"
                      className="text-[10px] text-zinc-600 hover:text-amber-500"
                      onClick={() => setReportFor(m.id)}
                    >
                      Жалоба
                    </button>
                  ) : null}
                </div>
              </div>
              {m.reply_to ? (
                <div
                  className={`mb-2 rounded-lg border px-2 py-1 text-xs ${
                    mine ? "border-emerald-500/30 bg-black/20" : "border-zinc-700 bg-black/20"
                  }`}
                >
                  <span className="text-zinc-300 line-clamp-2">{m.reply_to.body_snippet}</span>
                </div>
              ) : null}
              {m.body ? <p className="whitespace-pre-wrap break-words">{m.body}</p> : null}
            </div>
          );
        })}
        {!messages.length && ready && (
          <p className="text-zinc-500 text-sm">Пока тихо — можно начать с вопроса дня выше.</p>
        )}
        <div ref={bottomRef} />
      </div>

      {reportFor !== null && (
        <div className="border-t border-zinc-800 px-4 py-3 space-y-2 bg-zinc-900/80">
          <p className="text-xs text-zinc-400">Жалоба на сообщение #{reportFor}</p>
          <input
            className="w-full rounded-lg bg-zinc-950 border border-zinc-700 px-3 py-2 text-sm"
            value={reportReason}
            onChange={(e) => setReportReason(e.target.value)}
            placeholder="Кратко, что не так"
          />
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-lg bg-amber-600/80 px-3 py-1.5 text-sm"
              onClick={() => void submitReport()}
            >
              Отправить
            </button>
            <button
              type="button"
              className="text-sm text-zinc-500"
              onClick={() => {
                setReportFor(null);
                setReportReason("");
              }}
            >
              Отмена
            </button>
          </div>
        </div>
      )}

      {error && <p className="px-4 text-red-400 text-sm shrink-0">{error}</p>}
      <form
        onSubmit={send}
        className="border-t border-zinc-800 p-4 flex flex-col gap-2 shrink-0"
        style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}
      >
        {replyTo && (
          <div className="flex items-center justify-between gap-2 rounded-lg border border-zinc-700 bg-zinc-900/80 px-3 py-2 text-xs">
            <span className="text-zinc-300 line-clamp-2">Ответ: {replyTo.body_snippet}</span>
            <button
              type="button"
              className="text-zinc-500 shrink-0"
              onClick={() => setReplyTo(null)}
            >
              ✕
            </button>
          </div>
        )}
        <div className="flex flex-wrap gap-1.5">
          {STICKERS.map((s) => (
            <button
              key={s}
              type="button"
              className="text-lg leading-none px-1.5 py-0.5 rounded-md bg-zinc-900 border border-zinc-800 hover:border-zinc-600"
              onClick={() => setBody((b) => (b ? `${b}${s}` : s))}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            rows={1}
            className="flex-1 rounded-lg bg-zinc-900 border border-zinc-700 px-3 py-2 text-sm leading-5 resize-none overflow-hidden"
            value={body}
            onChange={(e) => setBody(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                if (body.trim()) void send(e as unknown as React.FormEvent);
                return;
              }
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (body.trim()) void send(e as unknown as React.FormEvent);
              }
            }}
            placeholder="Сообщение в группу…"
          />
          <button
            type="submit"
            disabled={!body.trim()}
            className="rounded-lg bg-emerald-500 text-zinc-950 px-4 py-2 text-sm font-medium disabled:opacity-40"
          >
            Отправить
          </button>
        </div>
        <p className="text-[10px] text-zinc-600">
          Лимит сервера: не больше ~15 сообщений в минуту на человека.
        </p>
        <p className="text-[10px] text-zinc-600">
          Enter — отправить · Shift+Enter — новая строка · Ctrl/⌘+Enter — отправить
        </p>
      </form>
      <BottomNav />
    </main>
  );
}
