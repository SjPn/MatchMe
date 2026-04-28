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
import { api, downloadBlob, getToken, postFormData } from "@/lib/api";

type Attachment = {
  original_name: string;
  mime: string;
  url: string;
};

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
  attachment?: Attachment | null;
  reply_to?: ReplyPreview | null;
};

const STICKERS = ["😀", "🔥", "👋", "✨", "💬", "🙌", "🤝", "❤️", "🎮", "☕"];

function mergeById(prev: Message[], incoming: Message[]): Message[] {
  const ids = new Set(prev.map((x) => x.id));
  const add = incoming.filter((x) => !ids.has(x.id));
  return add.length ? [...prev, ...add] : prev;
}

export default function ChatPage() {
  const params = useParams();
  const router = useRouter();
  const cid = Number(params.id);
  const [messages, setMessages] = useState<Message[]>([]);
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [meId, setMeId] = useState<number | null>(null);
  const [ready, setReady] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [replyTo, setReplyTo] = useState<ReplyPreview | null>(null);
  const [peerTyping, setPeerTyping] = useState(false);
  const [otherUserId, setOtherUserId] = useState<number | null>(null);
  const [peerName, setPeerName] = useState("");
  const [reportOpen, setReportOpen] = useState(false);
  const [reportReason, setReportReason] = useState("");
  const [modBusy, setModBusy] = useState(false);
  const [infoMsg, setInfoMsg] = useState<string | null>(null);
  const [showNotifyPrompt, setShowNotifyPrompt] = useState(false);
  const lastIdRef = useRef(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const messagesRef = useRef<Message[]>([]);
  const atBottomRef = useRef(true);
  const lastMarkedReadId = useRef(0);
  const fileRef = useRef<HTMLInputElement>(null);
  const typingIntervalRef = useRef<number | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [emojiOpen, setEmojiOpen] = useState(false);

  messagesRef.current = messages;

  function insertAtCursor(text: string) {
    const el = inputRef.current;
    if (!el) {
      setBody((b) => (b ? `${b}${text}` : text));
      return;
    }
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;
    const next = `${body.slice(0, start)}${text}${body.slice(end)}`;
    setBody(next);
    const caret = start + text.length;
    requestAnimationFrame(() => {
      try {
        el.focus();
        el.setSelectionRange(caret, caret);
      } catch {
        /* ignore */
      }
    });
  }

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
    if (!ready || !Number.isFinite(cid)) return;
    if (typeof document !== "undefined" && document.hidden) return;
    const box = scrollRef.current;
    if (!box || !isScrollNearBottom(box)) return;
    const list = messagesRef.current;
    const lastId = list.length ? list[list.length - 1].id : 0;
    if (lastId <= 0 || lastId <= lastMarkedReadId.current) return;
    lastMarkedReadId.current = lastId;
    void api(`/conversations/${cid}/read?last_message_id=${lastId}`, { method: "POST" });
  }, [ready, cid]);

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
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    if (!Number.isFinite(cid)) return;
    let cancelled = false;
    (async () => {
      try {
        const [me, peer, all] = await Promise.all([
          api<{ id: number }>("/auth/me"),
          api<{ other_user_id: number; other_display_name: string }>(`/conversations/${cid}/peer`),
          api<Message[]>(`/conversations/${cid}/messages`),
        ]);
        if (cancelled) return;
        setMeId(me.id);
        setOtherUserId(peer.other_user_id);
        setPeerName(peer.other_display_name || `Пользователь #${peer.other_user_id}`);
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
  }, [cid, router]);

  useEffect(() => {
    lastMarkedReadId.current = 0;
    atBottomRef.current = true;
  }, [cid]);

  useEffect(() => {
    if (typeof window !== "undefined" && typeof Notification !== "undefined") {
      setShowNotifyPrompt(Notification.permission === "default");
    }
  }, []);

  useEffect(() => {
    if (!ready || !Number.isFinite(cid)) return;

    function tick() {
      void (async () => {
        try {
          const box = scrollRef.current;
          const wasNearBottom = box ? isScrollNearBottom(box) : true;
          const [newer, typingRes] = await Promise.all([
            api<Message[]>(`/conversations/${cid}/messages?after_id=${lastIdRef.current}`),
            api<{ typing_user_ids: number[] }>(`/conversations/${cid}/typing`),
          ]);
          if (typeof document !== "undefined" && !document.hidden) {
            setPeerTyping((typingRes.typing_user_ids?.length ?? 0) > 0);
          }
          if (newer.length) {
            const me = meId;
            const fromPeer = me != null && newer.some((m) => m.sender_id !== me);
            if (fromPeer && typeof document !== "undefined" && document.hidden) {
              playSoftMessagePing();
              const last = newer[newer.length - 1];
              const snippet = (last.body || last.attachment?.original_name || "Сообщение").slice(0, 120);
              showChatNotificationIfAllowed(peerName || "Чат", snippet);
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
          /* тихо при фоновом опросе */
        }
      })();
    }

    const id = window.setInterval(tick, 2000);
    document.addEventListener("visibilitychange", tick);
    return () => {
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", tick);
    };
  }, [ready, cid, meId, peerName]);

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
    if (!ready || !Number.isFinite(cid)) return;
    if (typingIntervalRef.current) {
      window.clearInterval(typingIntervalRef.current);
      typingIntervalRef.current = null;
    }
    const text = body.trim();
    if (!text) return;
    void api(`/conversations/${cid}/typing`, { method: "POST" });
    typingIntervalRef.current = window.setInterval(() => {
      void api(`/conversations/${cid}/typing`, { method: "POST" });
    }, 2500);
    return () => {
      if (typingIntervalRef.current) {
        window.clearInterval(typingIntervalRef.current);
        typingIntervalRef.current = null;
      }
    };
  }, [body, ready, cid]);

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
      const payload: { body: string; reply_to_message_id?: number } = {
        body: body.trim(),
      };
      if (replyTo) payload.reply_to_message_id = replyTo.id;
      await api(`/conversations/${cid}/messages`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setBody("");
      setReplyTo(null);
      atBottomRef.current = true;
      hideKeyboard();
      setEmojiOpen(false);
      if (inputRef.current) {
        inputRef.current.style.height = "auto";
        inputRef.current.style.overflowY = "hidden";
      }
      const newer = await api<Message[]>(
        `/conversations/${cid}/messages?after_id=${lastIdRef.current}`
      );
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

  async function onPickFile(f: File | null) {
    if (!f) return;
    setError(null);
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      if (body.trim()) fd.append("caption", body.trim());
      if (replyTo) fd.append("reply_to_id", String(replyTo.id));
      const msg = await postFormData<Message>(`/conversations/${cid}/messages/upload`, fd);
      setBody("");
      setReplyTo(null);
      atBottomRef.current = true;
      hideKeyboard();
      setEmojiOpen(false);
      if (inputRef.current) {
        inputRef.current.style.height = "auto";
        inputRef.current.style.overflowY = "hidden";
      }
      setMessages((m) => [...m, msg]);
      lastIdRef.current = msg.id;
      if (fileRef.current) fileRef.current.value = "";
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки");
    } finally {
      setUploading(false);
    }
  }

  async function onBlockPeer() {
    if (otherUserId == null) return;
    if (!confirm("Заблокировать собеседника? Чат и лента скроют вас друг от друга.")) return;
    setModBusy(true);
    setError(null);
    try {
      await api(`/users/${otherUserId}/block`, { method: "POST" });
      router.replace("/conversations");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setModBusy(false);
    }
  }

  async function onReportPeer() {
    if (otherUserId == null || !reportReason.trim()) return;
    setModBusy(true);
    setError(null);
    try {
      await api(`/users/${otherUserId}/report`, {
        method: "POST",
        body: JSON.stringify({ reason: reportReason.trim() }),
      });
      setReportOpen(false);
      setReportReason("");
      setError(null);
      setInfoMsg("Жалоба отправлена.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setModBusy(false);
    }
  }

  async function saveAttachment(m: Message) {
    if (!m.attachment) return;
    try {
      const blob = await downloadBlob(m.attachment.url);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = m.attachment.original_name;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось скачать файл");
    }
  }

  return (
    <main className="mm-page-chat">
      <header className="border-b border-white/[0.06] bg-zinc-950/80 backdrop-blur-md px-4 py-3.5 flex items-center gap-4 shrink-0">
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
        <div className="flex flex-col min-w-0 flex-1">
          {otherUserId != null ? (
            <Link href={`/users/${otherUserId}`} className="font-medium truncate hover:text-emerald-300">
              {peerName || "Чат"}
            </Link>
          ) : (
            <span className="font-medium truncate">{peerName || "Чат"}</span>
          )}
          {peerTyping && (
            <span className="text-xs text-zinc-500 truncate">Собеседник печатает…</span>
          )}
          {otherUserId != null && (
            <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 text-[10px]">
              <button
                type="button"
                disabled={modBusy}
                className="text-amber-500/90 hover:text-amber-400 disabled:opacity-50"
                onClick={() => setReportOpen(true)}
              >
                Жалоба
              </button>
              <button
                type="button"
                disabled={modBusy}
                className="text-zinc-500 hover:text-red-400 disabled:opacity-50"
                onClick={() => void onBlockPeer()}
              >
                Заблокировать
              </button>
            </div>
          )}
        </div>
      </header>
      {reportOpen && otherUserId != null && (
        <div className="border-b border-zinc-800 px-4 py-3 space-y-2 bg-zinc-900/50">
          <textarea
            className="w-full rounded-lg bg-zinc-950 border border-zinc-700 px-3 py-2 text-xs min-h-[64px]"
            value={reportReason}
            onChange={(e) => setReportReason(e.target.value)}
            placeholder="Опишите нарушение"
          />
          <div className="flex gap-2">
            <button
              type="button"
              disabled={modBusy || !reportReason.trim()}
              className="rounded bg-amber-600/80 px-2 py-1 text-xs disabled:opacity-50"
              onClick={() => void onReportPeer()}
            >
              Отправить
            </button>
            <button
              type="button"
              className="text-xs text-zinc-500"
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
                {!mine ? (
                  <p className="text-xs text-zinc-500">Собеседник</p>
                ) : (
                  <p className="text-xs text-zinc-500">Вы</p>
                )}
                <button
                  type="button"
                  className="text-[10px] text-zinc-500 hover:text-emerald-400 shrink-0"
                  onClick={() =>
                    setReplyTo({
                      id: m.id,
                      sender_id: m.sender_id,
                      body_snippet: (m.body || m.attachment?.original_name || "вложение").slice(
                        0,
                        120
                      ),
                    })
                  }
                >
                  Ответить
                </button>
              </div>
              {m.reply_to ? (
                <div
                  className={`mb-2 rounded-lg border px-2 py-1 text-xs ${
                    mine ? "border-emerald-500/30 bg-black/20" : "border-zinc-700 bg-black/20"
                  }`}
                >
                  <span className="text-zinc-500">
                    {m.reply_to.sender_id === meId ? "Вы: " : "Собеседник: "}
                  </span>
                  <span className="text-zinc-300 line-clamp-2">{m.reply_to.body_snippet}</span>
                </div>
              ) : null}
              {m.body ? <p className="whitespace-pre-wrap break-words">{m.body}</p> : null}
              {m.attachment ? (
                <div className="mt-2 text-xs">
                  <a
                    href="#"
                    className="text-emerald-400 underline break-all"
                    onClick={(e) => {
                      e.preventDefault();
                      void saveAttachment(m);
                    }}
                  >
                    {m.attachment.original_name}
                  </a>
                  <span className="text-zinc-500 ml-2">({m.attachment.mime})</span>
                </div>
              ) : null}
            </div>
          );
        })}
        {!messages.length && ready && (
          <p className="text-zinc-500 text-sm">Пока пусто — напиши первым.</p>
        )}
        <div ref={bottomRef} />
      </div>
      {infoMsg && <p className="px-4 text-emerald-400/90 text-sm shrink-0">{infoMsg}</p>}
      {error && <p className="px-4 text-red-400 text-sm shrink-0">{error}</p>}
      <form
        onSubmit={send}
        className="border-t border-white/[0.06] bg-zinc-950/90 backdrop-blur-md p-4 flex flex-col gap-2 shrink-0 supports-[backdrop-filter]:bg-zinc-950/75"
        style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}
      >
        {replyTo && (
          <div className="flex items-center justify-between gap-2 rounded-lg border border-zinc-700 bg-zinc-900/80 px-3 py-2 text-xs">
            <div className="min-w-0">
              <span className="text-zinc-500">Ответ на: </span>
              <span className="text-zinc-300 line-clamp-2">{replyTo.body_snippet}</span>
            </div>
            <button
              type="button"
              className="text-zinc-500 hover:text-zinc-300 shrink-0"
              onClick={() => setReplyTo(null)}
              aria-label="Отменить ответ"
            >
              ✕
            </button>
          </div>
        )}
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="h-9 w-9 rounded-lg bg-zinc-900 border border-zinc-800 hover:border-zinc-600 text-lg leading-none flex items-center justify-center"
            onClick={() => setEmojiOpen((v) => !v)}
            aria-label="Смайлы"
          >
            🙂
          </button>
          {emojiOpen ? (
            <div className="flex flex-wrap gap-1.5">
              {STICKERS.map((s) => (
                <button
                  key={s}
                  type="button"
                  className="text-lg leading-none px-1.5 py-0.5 rounded-md bg-zinc-900 border border-zinc-800 hover:border-zinc-600"
                  onClick={() => {
                    insertAtCursor(s);
                    setEmojiOpen(false);
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          ) : null}
        </div>
        <div className="flex gap-2">
          <input
            type="file"
            ref={fileRef}
            className="text-xs text-zinc-400 file:mr-2 file:rounded file:border-0 file:bg-zinc-800 file:px-2 file:py-1"
            accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.zip,.doc,.docx,.xlsx"
            disabled={uploading}
            onChange={(e) => void onPickFile(e.target.files?.[0] ?? null)}
          />
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
                if (!uploading && body.trim()) void send(e as unknown as React.FormEvent);
              }
            }}
            placeholder="Текст или подпись к файлу…"
            disabled={uploading}
          />
          <button
            type="submit"
            disabled={uploading || !body.trim()}
            className="rounded-lg bg-emerald-500 text-zinc-950 px-4 py-2 text-sm font-medium disabled:opacity-40"
          >
            {uploading ? "…" : "Отправить"}
          </button>
        </div>
      </form>
      <BottomNav />
    </main>
  );
}
