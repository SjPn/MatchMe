"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { ThreadComposerSheet, ThreadPostOut } from "@/components/ThreadComposerSheet";
import { ThreadPostCard } from "@/components/ThreadPostCard";
import { ThreadActions } from "@/components/ThreadActions";
import { api, apiJsonWithEtag, getToken } from "@/lib/api";
import { useRouter } from "next/navigation";

type CursorPage = { items: ThreadPostOut[]; next_cursor: string | null };
type AxisOpt = { slug: string; name: string };

const POLL_BASE_MS = 6000;
const POLL_MAX_MS = 30000;

export default function TimelinePage() {
  const router = useRouter();
  const [tab, setTabState] = useState<"all" | "topics">("all");
  const [topic, setTopicState] = useState("");
  const [items, setItems] = useState<ThreadPostOut[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [axes, setAxes] = useState<AxisOpt[]>([]);
  const [openComposer, setOpenComposer] = useState(false);
  const [composerMode, setComposerMode] = useState<{ kind: "new" } | { kind: "quote"; target: ThreadPostOut }>({
    kind: "new",
  });
  const etagRef = useRef<string | null>(null);
  const pollDelayRef = useRef(POLL_BASE_MS);

  const qsTopic = useMemo(() => (topic ? `&topic=${encodeURIComponent(topic)}` : ""), [topic]);

  const loadFirst = useCallback(async () => {
    const r = await apiJsonWithEtag<CursorPage>(`/timeline?limit=20${qsTopic}`, etagRef.current);
    if (r.notModified) return;
    setItems(r.data.items);
    setNext(r.data.next_cursor);
    etagRef.current = r.etag;
  }, [qsTopic]);

  const loadMore = useCallback(async () => {
    if (!next) return;
    const p = await api<CursorPage>(`/timeline?limit=20&cursor=${encodeURIComponent(next)}${qsTopic}`);
    setItems((prev) => [...prev, ...p.items]);
    setNext(p.next_cursor);
  }, [next, qsTopic]);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        // Read initial state from URL on first mount (client-only, no suspense needed).
        try {
          const sp = new URLSearchParams(window.location.search);
          const t = (sp.get("tab") || "all").trim();
          const top = (sp.get("topic") || "").trim();
          setTabState(t === "topics" ? "topics" : "all");
          setTopicState(top);
        } catch {
          // ignore
        }
        await loadFirst();
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Ошибка");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router, loadFirst]);

  useEffect(() => {
    if (tab !== "topics") return;
    if (axes.length) return;
    let cancelled = false;
    void (async () => {
      try {
        const a = await api<AxisOpt[]>("/axes");
        if (!cancelled) setAxes(a);
      } catch {
        if (!cancelled) setAxes([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tab, axes.length]);

  useEffect(() => {
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
        const r = await apiJsonWithEtag<CursorPage>(`/timeline?limit=20${qsTopic}`, etagRef.current);
        if (cancelled) return;
        if (r.notModified) {
          pollDelayRef.current = Math.min(POLL_MAX_MS, Math.max(POLL_BASE_MS, Math.floor(pollDelayRef.current * 1.5)));
        } else {
          pollDelayRef.current = POLL_BASE_MS;
          etagRef.current = r.etag;
          setItems(r.data.items);
          setNext(r.data.next_cursor);
        }
      } catch {
        pollDelayRef.current = Math.min(POLL_MAX_MS, Math.max(POLL_BASE_MS, Math.floor(pollDelayRef.current * 1.35)));
      } finally {
        inFlight = false;
      }
      if (!cancelled) schedule(pollDelayRef.current);
    }

    schedule(POLL_BASE_MS);
    return () => {
      cancelled = true;
      if (timerId !== null) window.clearTimeout(timerId);
    };
  }, [qsTopic]);

  function setTab(nextTab: "all" | "topics") {
    setTabState(nextTab);
    if (nextTab === "all") setTopicState("");
    const p = new URLSearchParams(window.location.search);
    p.set("tab", nextTab);
    if (nextTab === "all") p.delete("topic");
    router.replace(`/timeline?${p.toString()}`);
  }

  function setTopic(nextTopic: string) {
    setTabState("topics");
    setTopicState(nextTopic);
    const p = new URLSearchParams(window.location.search);
    p.set("tab", "topics");
    if (nextTopic) p.set("topic", nextTopic);
    else p.delete("topic");
    router.replace(`/timeline?${p.toString()}`);
  }

  return (
    <main className="mm-page scrollbar-thin">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="mm-h2">Лента</h1>
          <p className="mm-lead mt-2">Посты и ответы — одна сущность, как в Threads. Ответы доступны по правилу ценностей поста.</p>
        </div>
        <button type="button" className="mm-btn-primary shrink-0 py-2.5 px-4 text-sm" onClick={() => setOpenComposer(true)}>
          Написать
        </button>
      </div>

      <div className="mt-6 flex gap-2">
        <button
          type="button"
          className={`rounded-full px-4 py-2 text-xs border ${
            tab === "all" ? "border-emerald-500/45 bg-emerald-500/10 text-emerald-200" : "border-zinc-700 text-zinc-400"
          }`}
          onClick={() => setTab("all")}
        >
          Все
        </button>
        <button
          type="button"
          className={`rounded-full px-4 py-2 text-xs border ${
            tab === "topics" ? "border-emerald-500/45 bg-emerald-500/10 text-emerald-200" : "border-zinc-700 text-zinc-400"
          }`}
          onClick={() => setTab("topics")}
        >
          Темы
        </button>
      </div>

      {tab === "topics" ? (
        <div className="mt-4">
          <p className="text-xs text-zinc-500 mb-2">Фильтр по теме (оси):</p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={`rounded-full px-3 py-1 text-xs border ${
                !topic ? "border-emerald-500/45 bg-emerald-500/10 text-emerald-200" : "border-zinc-700 text-zinc-400"
              }`}
              onClick={() => setTopic("")}
            >
              Все темы
            </button>
            {axes.map((a) => (
              <button
                key={a.slug}
                type="button"
                className={`rounded-full px-3 py-1 text-xs border ${
                  topic === a.slug
                    ? "border-emerald-500/45 bg-emerald-500/10 text-emerald-200"
                    : "border-zinc-700 text-zinc-400"
                }`}
                onClick={() => setTopic(a.slug)}
              >
                {a.name}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {error ? <p className="mt-6 mm-error">{error}</p> : null}

      <ul className="mt-8 flex flex-col gap-4">
        {items.map((p) => (
          <li key={p.id}>
            <div className="mm-card py-4">
              <ThreadPostCard post={p} compact withCard={false} />
              <ThreadActions
                post={p}
                onPostChange={(nextPost) =>
                  setItems((prev) => prev.map((x) => (x.id === nextPost.id ? nextPost : x)))
                }
                onReply={() => router.push(`/posts/${p.id}`)}
                onQuote={() => {
                  setComposerMode({ kind: "quote", target: p });
                  setOpenComposer(true);
                }}
                onRepost={() => void loadFirst()}
              />
            </div>
          </li>
        ))}
      </ul>

      {!items.length && !error ? <p className="mm-empty mt-6">Пока нет постов — создайте первый.</p> : null}

      {next ? (
        <div className="mt-6">
          <button type="button" className="mm-btn-secondary w-full py-3" onClick={() => void loadMore()}>
            Показать ещё
          </button>
        </div>
      ) : null}

      <ThreadComposerSheet
        open={openComposer}
        mode={composerMode.kind === "new" ? { kind: "new" } : { kind: "quote", target: composerMode.target }}
        onClose={() => setOpenComposer(false)}
        onCreated={(created) => setItems((prev) => [created, ...prev])}
      />

      <BottomNav />
    </main>
  );
}

