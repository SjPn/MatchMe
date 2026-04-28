"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { ChatComposer } from "@/components/chat/ChatComposer";
import { MessageBubble } from "@/components/chat/MessageBubble";
import {
  isScrollNearBottom,
  playSoftMessagePing,
  requestNotificationPermission,
  showChatNotificationIfAllowed,
} from "@/lib/chatClient";
import { useChatPolling } from "@/lib/hooks/useChatPolling";
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
const EMOJIS = ["😀", "🔥", "👋", "✨", "💬", "🙌", "🤝", "❤️", "🎮", "☕"];

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
  const scrollRef = useRef<HTMLDivElement>(null);
  const typingIntervalRef = useRef<number | null>(null);
  const messagesRef = useRef<Message[]>([]);
  messagesRef.current = messages;
  const didInitialScrollRef = useRef<{ cid: number; done: boolean }>({ cid: -1, done: false });

  const tryMarkRead = useCallback(() => {
    if (!ready || !Number.isFinite(cid)) return;
    if (typeof document !== "undefined" && document.hidden) return;
    const box = scrollRef.current;
    if (!box || !isScrollNearBottom(box)) return;
    const list = messagesRef.current;
    const lastId = list.length ? list[list.length - 1].id : 0;
    if (lastId <= 0) return;
    void api(`/conversations/${cid}/read?last_message_id=${lastId}`, { method: "POST" });
  }, [ready, cid]);

  const polling = useChatPolling<Message>({
    enabled: ready && Number.isFinite(cid),
    intervalMs: 2000,
    scrollRef,
    isTabHidden: () => (typeof document !== "undefined" ? document.hidden : false),
    isNearBottom: (el) => isScrollNearBottom(el, 96),
    getMessages: () => messagesRef.current,
    getId: (m) => m.id,
    merge: mergeById,
    setMessages,
    fetchNewer: (afterId) => api<Message[]>(`/conversations/${cid}/messages?after_id=${afterId}`),
    fetchSidecar: async () => {
      const typingRes = await api<{ typing_user_ids: number[] }>(`/conversations/${cid}/typing`);
      if (typeof document !== "undefined" && !document.hidden) {
        setPeerTyping((typingRes.typing_user_ids?.length ?? 0) > 0);
      }
    },
    onIncoming: ({ newer }) => {
      const me = meId;
      const fromPeer = me != null && newer.some((m) => m.sender_id !== me);
      if (fromPeer && typeof document !== "undefined" && document.hidden) {
        playSoftMessagePing();
        const last = newer[newer.length - 1];
        const snippet = (last.body || last.attachment?.original_name || "Сообщение").slice(0, 120);
        showChatNotificationIfAllowed(peerName || "Чат", snippet);
      }
    },
    markRead: (lastMessageId) => {
      void api(`/conversations/${cid}/read?last_message_id=${lastMessageId}`, { method: "POST" });
    },
  });

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

  useLayoutEffect(() => {
    // On open (or switching dialogs), jump to the latest messages once.
    // We tie this to messages.length so it runs after the list is actually rendered.
    if (!ready || !Number.isFinite(cid)) return;
    if (didInitialScrollRef.current.cid !== cid) {
      didInitialScrollRef.current = { cid, done: false };
    }
    if (didInitialScrollRef.current.done) return;
    const box = scrollRef.current;
    if (!box) return;
    if (messages.length < 1) return;
    didInitialScrollRef.current.done = true;
    polling.atBottomRef.current = true;
    // Double-rAF makes sure layout is settled (fonts/safe-area/etc.)
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        try {
          box.scrollTop = box.scrollHeight;
        } catch {
          /* ignore */
        }
        polling.tryMarkReadNow();
      });
    });
  }, [ready, cid, messages.length, polling]);

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
      polling.atBottomRef.current = true;
      const newer = await api<Message[]>(
        `/conversations/${cid}/messages?after_id=${polling.lastIdRef.current}`
      );
      if (newer.length) {
        setMessages((m) => {
          const merged = mergeById(m, newer);
          if (merged !== m) polling.lastIdRef.current = merged[merged.length - 1].id;
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
      polling.atBottomRef.current = true;
      setMessages((m) => [...m, msg]);
      polling.lastIdRef.current = msg.id;
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
        onPointerDown={() => {
          // composer handles keyboard too, but tapping the list should also hide it
          try {
            (document.activeElement as HTMLElement | null)?.blur?.();
          } catch {
            /* ignore */
          }
        }}
        onScroll={() => {
          polling.onScroll();
        }}
      >
        {messages.map((m) => {
          const mine = meId !== null && m.sender_id === meId;
          const rp = m.reply_to;
          return (
            <MessageBubble
              key={m.id}
              mine={mine}
              headerLeft={mine ? "Вы" : "Собеседник"}
              onReply={() =>
                setReplyTo({
                  id: m.id,
                  sender_id: m.sender_id,
                  body_snippet: (m.body || m.attachment?.original_name || "вложение").slice(0, 120),
                })
              }
              body={m.body}
              replyTo={rp ?? null}
              replyPrefix={rp ? (rp.sender_id === meId ? "Вы: " : "Собеседник: ") : null}
              attachment={m.attachment ?? null}
              onAttachmentClick={() => void saveAttachment(m)}
            />
          );
        })}
        {!messages.length && ready && (
          <p className="text-zinc-500 text-sm">Пока пусто — напиши первым.</p>
        )}
      </div>
      {infoMsg && <p className="px-4 text-emerald-400/90 text-sm shrink-0">{infoMsg}</p>}
      {error && <p className="px-4 text-red-400 text-sm shrink-0">{error}</p>}
      <form onSubmit={send} className="contents">
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
        <ChatComposer
          value={body}
          onChange={setBody}
          onSend={() => {
            // Use the same submit handler
            void send({ preventDefault() {} } as unknown as React.FormEvent);
          }}
          disabled={uploading}
          placeholder="Сообщение"
          maxLines={7}
          emojis={EMOJIS}
          emojiButtonOnFileRow
          file={{
            accept: ".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.zip,.doc,.docx,.xlsx",
            disabled: uploading,
            onPick: (f) => void onPickFile(f),
          }}
        />
      </form>
      <BottomNav />
    </main>
  );
}
