"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { DiscussionThumbImage } from "@/components/DiscussionThumbImage";
import { apiJsonWithEtag, getToken } from "@/lib/api";

type PostRow = {
  id: number;
  title: string;
  body_preview: string;
  theme_axes: { slug: string; name: string }[];
  author_display_name: string | null;
  is_system: boolean;
  image_url: string | null;
  comment_count: number;
  created_at: string;
};

const LIST_POLL_BASE_MS = 6000;
const LIST_POLL_MAX_MS = 32000;

export default function DiscussionsListPage() {
  const router = useRouter();
  const [posts, setPosts] = useState<PostRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const listPollDelayRef = useRef(LIST_POLL_BASE_MS);
  const listEtagRef = useRef<string | null>(null);

  const load = useCallback(async () => {
    const r = await apiJsonWithEtag<PostRow[]>("/discussions/posts?limit=40", listEtagRef.current);
    if (r.notModified) return;
    setPosts(r.data);
    listEtagRef.current = r.etag;
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
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
  }, [router, load]);

  useEffect(() => {
    let cancelled = false;
    let timerId: number | null = null;
    let inFlight = false;

    listPollDelayRef.current = LIST_POLL_BASE_MS;

    const schedule = (ms: number) => {
      if (timerId !== null) window.clearTimeout(timerId);
      timerId = window.setTimeout(() => void run(), ms);
    };

    async function run() {
      if (cancelled) return;
      if (typeof document !== "undefined" && document.hidden) {
        schedule(listPollDelayRef.current);
        return;
      }
      if (inFlight) {
        schedule(LIST_POLL_BASE_MS);
        return;
      }
      inFlight = true;
      try {
        const r = await apiJsonWithEtag<PostRow[]>("/discussions/posts?limit=40", listEtagRef.current);
        if (cancelled) return;
        if (r.notModified) {
          listPollDelayRef.current = Math.min(
            LIST_POLL_MAX_MS,
            Math.max(LIST_POLL_BASE_MS, Math.floor(listPollDelayRef.current * 1.5))
          );
        } else {
          listPollDelayRef.current = LIST_POLL_BASE_MS;
          listEtagRef.current = r.etag;
          setPosts(r.data);
        }
      } catch {
        listPollDelayRef.current = Math.min(
          LIST_POLL_MAX_MS,
          Math.max(LIST_POLL_BASE_MS, Math.floor(listPollDelayRef.current * 1.35))
        );
      } finally {
        inFlight = false;
      }
      if (!cancelled) schedule(listPollDelayRef.current);
    }

    schedule(LIST_POLL_BASE_MS);

    const onVis = () => {
      if (document.hidden || cancelled) return;
      listPollDelayRef.current = LIST_POLL_BASE_MS;
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
  }, []);

  return (
    <main className="mm-page scrollbar-thin">
      <div className="flex justify-between items-start gap-4">
        <div className="min-w-0">
          <h1 className="mm-h2">Обсуждения по темам</h1>
          <p className="mm-lead mt-2">
            Посты привязаны к осям ценностей. Комментировать могут те, чей профиль подходит под правила
            темы.
          </p>
        </div>
        <Link href="/discussions/new" className="mm-btn-primary shrink-0 py-2.5 px-4 text-sm">
          Новый пост
        </Link>
      </div>

      {error ? <p className="mt-6 mm-error">{error}</p> : null}

      <ul className="mt-8 flex flex-col gap-4">
        {posts.map((p) => (
          <li key={p.id}>
            <Link href={`/discussions/${p.id}`} className="block mm-card py-5">
              <div className="flex justify-between gap-3">
                <p className="font-medium text-zinc-100 leading-snug">{p.title}</p>
                {p.image_url ? <DiscussionThumbImage postId={p.id} title={p.title} /> : null}
              </div>
              <p className="text-sm text-zinc-400 mt-2 line-clamp-3">{p.body_preview}</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {p.theme_axes.map((a) => (
                  <span
                    key={a.slug}
                    className="text-[10px] rounded-full border border-zinc-700 px-2 py-0.5 text-zinc-500"
                  >
                    {a.name}
                  </span>
                ))}
              </div>
              <p className="text-xs text-zinc-600 mt-2">
                {p.author_display_name ?? "—"} · {p.comment_count} комм.
              </p>
            </Link>
          </li>
        ))}
      </ul>

      {!posts.length && !error ? <p className="mm-empty mt-6">Пока нет постов — создайте первый.</p> : null}

      <BottomNav />
    </main>
  );
}
