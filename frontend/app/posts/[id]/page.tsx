"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { BottomNav } from "@/components/BottomNav";
import { ThreadComposerSheet, ThreadPostOut } from "@/components/ThreadComposerSheet";
import { ThreadPostCard } from "@/components/ThreadPostCard";
import { ThreadActions } from "@/components/ThreadActions";
import { api, getToken } from "@/lib/api";

type Detail = {
  post: ThreadPostOut;
  parents: ThreadPostOut[];
  replies: ThreadPostOut[];
  next_replies_cursor: string | null;
};

type CursorPage = { items: ThreadPostOut[]; next_cursor: string | null };

export default function PostDetailPage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const postId = Number(params?.id);

  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [canReply, setCanReply] = useState<{ ok: boolean; reason: string }>({ ok: false, reason: "" });
  const [openReply, setOpenReply] = useState(false);
  const [openQuote, setOpenQuote] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const load = useCallback(async () => {
    const d = await api<Detail>(`/posts/${postId}?replies_limit=20`);
    setDetail(d);
    try {
      const cr = await api<{ can_reply: boolean; reason: string }>(`/posts/${postId}/can-reply`);
      setCanReply({ ok: cr.can_reply, reason: cr.reason || "" });
    } catch {
      setCanReply({ ok: false, reason: "" });
    }
  }, [postId]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    if (!postId || Number.isNaN(postId)) {
      setError("Некорректный id поста");
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        await load();
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Ошибка");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router, postId, load]);

  const threadTitle = useMemo(() => {
    if (!detail) return "Пост";
    const a = detail.post.author.display_name || (detail.post.is_system ? "MatchMe" : "—");
    return `Пост · ${a}`;
  }, [detail]);

  async function loadMoreReplies() {
    if (!detail?.next_replies_cursor) return;
    setLoadingMore(true);
    try {
      const p = await api<CursorPage>(
        `/posts/${postId}/replies?limit=20&cursor=${encodeURIComponent(detail.next_replies_cursor)}`
      );
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              replies: [...prev.replies, ...p.items],
              next_replies_cursor: p.next_cursor,
            }
          : prev
      );
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <main className="mm-page-fixed scrollbar-thin">
      <header className="pt-6 pb-4">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs text-zinc-500">
              <Link href="/timeline" className="mm-link">
                ← Лента
              </Link>
            </p>
            <h1 className="mm-h2 mt-2">{threadTitle}</h1>
          </div>
          <button
            type="button"
            className={`mm-btn-primary py-2.5 px-4 text-sm ${!canReply.ok ? "opacity-60" : ""}`}
            onClick={() => canReply.ok && setOpenReply(true)}
            disabled={!detail || !canReply.ok}
            title={!canReply.ok ? canReply.reason : "Ответить"}
          >
            Ответить
          </button>
        </div>
        {!canReply.ok && canReply.reason ? <p className="mt-3 text-xs text-zinc-500">{canReply.reason}</p> : null}
      </header>

      <section className="flex-1 min-h-0 overflow-y-auto pb-24">
        {error ? <p className="mm-error">{error}</p> : null}

        {detail ? (
          <div className="space-y-4">
            {detail.parents.length ? (
              <div className="space-y-3">
                <p className="text-xs text-zinc-600">Контекст</p>
                {detail.parents.map((p) => (
                  <ThreadPostCard key={p.id} post={p} compact />
                ))}
                <div className="mm-divider" />
              </div>
            ) : null}

            <div>
              <p className="text-xs text-zinc-600 mb-3">Пост</p>
              <div className="mm-card py-4">
                <ThreadPostCard post={detail.post} withCard={false} />
                <ThreadActions
                  post={detail.post}
                  onPostChange={(nextPost) => setDetail((prev) => (prev ? { ...prev, post: nextPost } : prev))}
                  onReply={() => canReply.ok && setOpenReply(true)}
                  onQuote={() => setOpenQuote(true)}
                  onRepost={() => void load()}
                />
              </div>
            </div>

            <div className="mm-divider" />

            <div>
              <p className="text-xs text-zinc-600 mb-3">Ответы</p>
              {detail.replies.length ? (
                <ul className="space-y-3">
                  {detail.replies.map((r) => (
                    <li key={r.id}>
                      <div className="mm-card py-4">
                        <ThreadPostCard post={r} compact withCard={false} href={`/threads/${r.id}`} />
                        <div className="mt-3">
                          <Link href={`/threads/${r.id}`} className="mm-link text-xs">
                            Открыть ветку →
                          </Link>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-zinc-500 py-8 text-center">Пока нет ответов.</p>
              )}
              {detail.next_replies_cursor ? (
                <button
                  type="button"
                  className="mt-4 mm-btn-secondary w-full py-3"
                  disabled={loadingMore}
                  onClick={() => void loadMoreReplies()}
                >
                  {loadingMore ? "…" : "Ещё ответы"}
                </button>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>

      {detail ? (
        <>
          <ThreadComposerSheet
            open={openReply}
            mode={{ kind: "reply", parent: detail.post }}
            onClose={() => setOpenReply(false)}
            onCreated={(created) =>
              setDetail((prev) => (prev ? { ...prev, replies: [created, ...prev.replies] } : prev))
            }
          />
          <ThreadComposerSheet
            open={openQuote}
            mode={{ kind: "quote", target: detail.post }}
            onClose={() => setOpenQuote(false)}
          />
        </>
      ) : null}

      <BottomNav />
    </main>
  );
}

