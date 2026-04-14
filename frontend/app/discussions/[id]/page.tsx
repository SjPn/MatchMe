"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { DiscussionCoverImage } from "@/components/DiscussionCoverImage";
import { api, apiJsonWithEtag, getToken } from "@/lib/api";

type Post = {
  id: number;
  title: string;
  body: string;
  theme_axes: { slug: string; name: string }[];
  author_display_name: string | null;
  is_system: boolean;
  image_url: string | null;
  comment_count: number;
  created_at: string;
};

type ReplyPreview = {
  id: number;
  user_id: number;
  display_name: string;
  body_snippet: string;
};

type CommentRow = {
  id: number;
  user_id: number;
  display_name: string;
  body: string;
  reply_to_comment_id: number | null;
  reply_to: ReplyPreview | null;
  created_at: string;
};

type ReplyDraft = {
  id: number;
  display_name: string;
  body_snippet: string;
};

type CanComment = { can_comment: boolean; reason: string };

/** Базовый интервал опроса новых комментариев; при отсутствии новых — увеличивается (до POLL_MAX_MS). */
const POLL_BASE_MS = 5000;
const POLL_MAX_MS = 28000;

function mergeById(prev: CommentRow[], incoming: CommentRow[]): CommentRow[] {
  const ids = new Set(prev.map((x) => x.id));
  const add = incoming.filter((x) => !ids.has(x.id));
  return add.length ? [...prev, ...add] : prev;
}

function snippetLocal(body: string, n = 120): string {
  const t = body.trim().replace(/\s+/g, " ");
  if (t.length <= n) return t;
  return `${t.slice(0, n - 1)}…`;
}

export default function DiscussionDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);
  const [post, setPost] = useState<Post | null>(null);
  const [comments, setComments] = useState<CommentRow[]>([]);
  const [perm, setPerm] = useState<CanComment | null>(null);
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [ready, setReady] = useState(false);
  const [replyTo, setReplyTo] = useState<ReplyDraft | null>(null);
  const lastIdRef = useRef(0);
  const commentEtagRef = useRef<string | null>(null);
  const pollDelayRef = useRef(POLL_BASE_MS);

  const refreshPost = useCallback(async () => {
    try {
      const p = await api<Post>(`/discussions/posts/${id}`);
      setPost(p);
    } catch {
      /* фон */
    }
  }, [id]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    if (!Number.isFinite(id)) return;
    let cancelled = false;
    void (async () => {
      try {
        const [p, cr, k] = await Promise.all([
          api<Post>(`/discussions/posts/${id}`),
          apiJsonWithEtag<CommentRow[]>(`/discussions/posts/${id}/comments`, null),
          api<CanComment>(`/discussions/posts/${id}/can-comment`),
        ]);
        if (!cancelled) {
          setPost(p);
          if (!cr.notModified) {
            setComments(cr.data);
            commentEtagRef.current = cr.etag;
            lastIdRef.current = cr.data.length ? Math.max(...cr.data.map((x) => x.id)) : 0;
          }
          setPerm(k);
          setReady(true);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Ошибка");
        setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, router]);

  useEffect(() => {
    if (!ready || !Number.isFinite(id) || !post) return;

    let cancelled = false;
    let timerId: number | null = null;
    let inFlight = false;

    pollDelayRef.current = POLL_BASE_MS;

    const schedule = (ms: number) => {
      if (timerId !== null) window.clearTimeout(timerId);
      timerId = window.setTimeout(() => void run(), ms);
    };

    async function run() {
      if (cancelled) return;
      if (typeof document !== "undefined" && document.hidden) {
        schedule(pollDelayRef.current);
        return;
      }
      if (inFlight) {
        schedule(POLL_BASE_MS);
        return;
      }
      inFlight = true;
      try {
        const r = await apiJsonWithEtag<CommentRow[]>(
          `/discussions/posts/${id}/comments?after_id=${lastIdRef.current}`,
          commentEtagRef.current
        );
        if (cancelled) return;
        if (r.notModified) {
          pollDelayRef.current = Math.min(
            POLL_MAX_MS,
            Math.max(POLL_BASE_MS, Math.floor(pollDelayRef.current * 1.55))
          );
        } else {
          commentEtagRef.current = r.etag;
          if (r.data.length) {
            pollDelayRef.current = POLL_BASE_MS;
            setComments((m) => {
              const merged = mergeById(m, r.data);
              if (merged !== m) {
                lastIdRef.current = merged.reduce((mx, x) => Math.max(mx, x.id), 0);
              }
              return merged;
            });
            void refreshPost();
          } else {
            pollDelayRef.current = Math.min(
              POLL_MAX_MS,
              Math.max(POLL_BASE_MS, Math.floor(pollDelayRef.current * 1.55))
            );
          }
        }
      } catch {
        pollDelayRef.current = Math.min(
          POLL_MAX_MS,
          Math.max(POLL_BASE_MS, Math.floor(pollDelayRef.current * 1.4))
        );
      } finally {
        inFlight = false;
      }
      if (!cancelled) schedule(pollDelayRef.current);
    }

    schedule(POLL_BASE_MS);

    const onVis = () => {
      if (document.hidden || cancelled) return;
      pollDelayRef.current = POLL_BASE_MS;
      if (timerId !== null) {
        window.clearTimeout(timerId);
        timerId = null;
      }
      void run();
    };
    document.addEventListener("visibilitychange", onVis);

    return () => {
      cancelled = true;
      if (timerId !== null) window.clearTimeout(timerId);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [ready, id, post, refreshPost]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!body.trim() || !perm?.can_comment) return;
    setSending(true);
    setError(null);
    pollDelayRef.current = POLL_BASE_MS;
    try {
      const payload: { body: string; reply_to_comment_id?: number } = {
        body: body.trim(),
      };
      if (replyTo) payload.reply_to_comment_id = replyTo.id;
      await api<CommentRow>(`/discussions/posts/${id}/comments`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setBody("");
      setReplyTo(null);
      const cr = await apiJsonWithEtag<CommentRow[]>(
        `/discussions/posts/${id}/comments?after_id=${lastIdRef.current}`,
        commentEtagRef.current
      );
      if (!cr.notModified) {
        commentEtagRef.current = cr.etag;
        if (cr.data.length) {
          setComments((m) => {
            const merged = mergeById(m, cr.data);
            if (merged !== m) {
              lastIdRef.current = merged.reduce((mx, x) => Math.max(mx, x.id), 0);
            }
            return merged;
          });
        }
      }
      const [k, p] = await Promise.all([
        api<CanComment>(`/discussions/posts/${id}/can-comment`),
        api<Post>(`/discussions/posts/${id}`),
      ]);
      setPerm(k);
      setPost(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setSending(false);
    }
  }

  if (error && !post) {
    return (
      <main className="min-h-screen flex items-center justify-center px-6">
        <p className="mm-error text-center max-w-sm">{error}</p>
      </main>
    );
  }

  if (!post) {
    return (
      <main className="min-h-screen flex items-center justify-center text-zinc-500">
        <span className="inline-flex items-center gap-2 text-sm">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" />
          Загрузка…
        </span>
      </main>
    );
  }

  return (
    <main className="mm-page-fixed">
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-y-contain scrollbar-thin pt-6 pb-2">
          <Link href="/discussions" className="text-sm text-zinc-500 hover:text-emerald-400/90 transition-colors">
            ← К обсуждениям
          </Link>

          <h1 className="mm-h2 mt-4 leading-snug">{post.title}</h1>
          <p className="text-xs text-zinc-500 mt-1">
            {post.author_display_name ?? "—"} · {new Date(post.created_at).toLocaleString()}
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            {post.theme_axes.map((a) => (
              <span
                key={a.slug}
                className="mm-badge-accent text-[10px] py-0.5"
              >
                {a.name}
              </span>
            ))}
          </div>

          {post.image_url ? (
            <div className="mt-4">
              <DiscussionCoverImage postId={post.id} title={post.title} />
            </div>
          ) : null}

          <article className="mt-5 text-sm text-zinc-300/95 whitespace-pre-wrap leading-relaxed">{post.body}</article>

          <section className="mt-10">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-zinc-500 mb-3" id="comments-heading">
              Комментарии
            </h2>
            <ul className="space-y-3" aria-labelledby="comments-heading">
              {comments.map((c) => (
                <li key={c.id} className="mm-card-static px-3 py-3 hover:border-zinc-700/90 transition-colors">
                  <div className="flex justify-between items-start gap-2">
                    <p className="text-xs font-medium text-zinc-400">{c.display_name}</p>
                    <button
                      type="button"
                      className="text-[10px] font-medium text-zinc-500 hover:text-emerald-400 shrink-0"
                      aria-label={`Ответить на комментарий ${c.display_name}`}
                      onClick={() =>
                        setReplyTo({
                          id: c.id,
                          display_name: c.display_name,
                          body_snippet: snippetLocal(c.body),
                        })
                      }
                    >
                      Ответить
                    </button>
                  </div>
                  {c.reply_to ? (
                    <div className="mt-2 rounded-lg border border-zinc-700/80 bg-black/25 px-2 py-1.5 text-xs">
                      <span className="text-zinc-500">{c.reply_to.display_name}: </span>
                      <span className="text-zinc-400 line-clamp-2">{c.reply_to.body_snippet}</span>
                    </div>
                  ) : null}
                  <p className="text-sm text-zinc-300 mt-1 whitespace-pre-wrap">{c.body}</p>
                </li>
              ))}
            </ul>
            {!comments.length ? <p className="text-zinc-600 text-sm py-2">Пока нет комментариев.</p> : null}
          </section>

          {perm && !perm.can_comment ? (
            <p className="mt-6 text-sm text-amber-200/95 border border-amber-500/25 rounded-xl px-4 py-3 bg-amber-950/20">
              {perm.reason || "Комментирование недоступно."}
            </p>
          ) : null}

          {error && post ? <p className="mt-4 mm-error">{error}</p> : null}
        </div>

        {perm?.can_comment ? (
          <form
            onSubmit={onSubmit}
            className="shrink-0 border-t border-white/[0.06] bg-zinc-950/90 px-0 pt-3 pb-[max(0.5rem,env(safe-area-inset-bottom))] space-y-2 backdrop-blur-xl supports-[backdrop-filter]:bg-zinc-950/80"
          >
            {replyTo ? (
              <div className="flex items-center justify-between gap-2 rounded-xl border border-zinc-700/80 bg-zinc-900/70 px-3 py-2 text-xs">
                <div className="min-w-0">
                  <span className="text-zinc-500">Ответ на </span>
                  <span className="text-zinc-400">{replyTo.display_name}: </span>
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
            ) : null}
            <div className="flex gap-2 items-end">
              <textarea
                className="mm-input flex-1 min-h-[52px] max-h-40 resize-y py-2.5"
                rows={2}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Комментарий…"
                maxLength={4000}
                aria-label={replyTo ? `Ответ для ${replyTo.display_name}` : "Текст комментария"}
              />
              <button
                type="submit"
                disabled={sending || !body.trim()}
                className="mm-btn-primary shrink-0 self-end min-h-[52px] px-3 text-xs sm:text-sm max-w-[6rem] leading-tight py-2 disabled:opacity-40"
              >
                {sending ? "…" : "Отправить"}
              </button>
            </div>
          </form>
        ) : null}
      </div>

      <BottomNav />
    </main>
  );
}
