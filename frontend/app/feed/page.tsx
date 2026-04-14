"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { api, getToken } from "@/lib/api";

type Insight = { axis: string; slug: string; detail: string };

type Card = {
  user_id: number;
  display_name: string;
  avatar_url?: string | null;
  about_me?: string | null;
  match_percent: number;
  base_match_percent: number;
  weighted_used: boolean;
  soft_penalty_notes: string[];
  agreements: Insight[];
  differences: Insight[];
  keyword_hit?: { field: string; snippet: string; matched_terms: string[] } | null;
  dealbreaker_hit?: boolean;
};

type LikeInboxRow = {
  from_user_id: number;
  from_display_name: string;
};

type AxisOpt = { slug: string; name: string };

type FeedPrefs = {
  axis_weights: Record<string, number>;
  soft_priority_slugs: string[];
  dealbreaker_slugs: string[];
  available_axes: AxisOpt[];
};

type FeedMeta = {
  api_database: string;
  other_users_total: number;
  visible_not_blocked: number;
};

function initialsFrom(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function FeedAvatar({ name, url }: { name: string; url?: string | null }) {
  const [broken, setBroken] = useState(false);
  const showImg = Boolean(url && !broken);
  const initials = initialsFrom(name);
  return (
    <div className="h-14 w-14 rounded-full overflow-hidden border border-emerald-500/20 ring-2 ring-black/20 shrink-0 bg-gradient-to-br from-emerald-900/70 to-zinc-900 flex items-center justify-center shadow-lg shadow-black/30">
      {showImg ? (
        <Image
          src={url as string}
          alt={`Аватар ${name}`}
          width={56}
          height={56}
          className="h-full w-full object-cover"
          unoptimized
          onError={() => setBroken(true)}
        />
      ) : (
        <span className="text-sm font-semibold text-emerald-100/90">{initials}</span>
      )}
    </div>
  );
}

export default function FeedPage() {
  const router = useRouter();
  const [cards, setCards] = useState<Card[]>([]);
  const [likeInbox, setLikeInbox] = useState<LikeInboxRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [search, setSearch] = useState("");
  const [searchActive, setSearchActive] = useState("");
  const [prefsOpen, setPrefsOpen] = useState(false);
  const [prefs, setPrefs] = useState<FeedPrefs | null>(null);
  const [weightsDraft, setWeightsDraft] = useState<Record<string, number>>({});
  const [softDraft, setSoftDraft] = useState<string[]>([]);
  const [dealDraft, setDealDraft] = useState<string[]>([]);
  const [prefsMsg, setPrefsMsg] = useState<string | null>(null);
  const [prefsSaving, setPrefsSaving] = useState(false);
  const [feedMeta, setFeedMeta] = useState<FeedMeta | null>(null);
  /** Первый запуск loadFeed после ready даёт эффект из bootstrap — не дублируем. */
  const skipNextFeedEffect = useRef(true);

  const loadFeed = useCallback(async (qActive: string) => {
    const params = new URLSearchParams();
    params.set("limit", "50");
    if (qActive.trim()) params.set("q", qActive.trim());
    const data = await api<Card[]>(`/feed?${params.toString()}`);
    setCards(data);
    if (data.length === 0) {
      try {
        const meta = await api<FeedMeta>("/feed/meta");
        setFeedMeta(meta);
      } catch {
        setFeedMeta(null);
      }
    } else {
      setFeedMeta(null);
    }
  }, []);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const me = await api<{ onboarding_step: string; server_db_kind?: string }>("/auth/me");
        if (cancelled) return;
        if (me.onboarding_step !== "test_completed") {
          router.replace("/test");
          return;
        }
        const feedParams = new URLSearchParams();
        feedParams.set("limit", "50");
        const [inbox, fp, cards] = await Promise.all([
          api<LikeInboxRow[]>("/likes/inbox"),
          api<FeedPrefs>("/me/feed-preferences"),
          api<Card[]>(`/feed?${feedParams.toString()}`),
        ]);
        if (cancelled) return;
        setLikeInbox(inbox);
        setPrefs(fp);
        setWeightsDraft({ ...fp.axis_weights });
        setSoftDraft([...fp.soft_priority_slugs]);
        setDealDraft([...(fp.dealbreaker_slugs ?? [])]);
        setCards(cards);
        if (cards.length === 0) {
          try {
            const meta = await api<FeedMeta>("/feed/meta");
            if (!cancelled) setFeedMeta(meta);
          } catch {
            if (!cancelled) setFeedMeta(null);
          }
        } else {
          setFeedMeta(null);
        }
        setReady(true);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Ошибка");
          setReady(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  useEffect(() => {
    if (!ready) return;
    if (skipNextFeedEffect.current) {
      skipNextFeedEffect.current = false;
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        await loadFeed(searchActive);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Ошибка");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [ready, searchActive, loadFeed]);

  async function savePrefs() {
    setPrefsMsg(null);
    setPrefsSaving(true);
    try {
      const next = await api<FeedPrefs>("/me/feed-preferences", {
        method: "PUT",
        body: JSON.stringify({
          axis_weights: weightsDraft,
          soft_priority_slugs: softDraft,
          dealbreaker_slugs: dealDraft,
        }),
      });
      setPrefs(next);
      setWeightsDraft({ ...next.axis_weights });
      setSoftDraft([...next.soft_priority_slugs]);
      setDealDraft([...next.dealbreaker_slugs]);
      setPrefsMsg("Сохранено — лента пересчитана.");
      await loadFeed(searchActive);
    } catch (e) {
      setPrefsMsg(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setPrefsSaving(false);
    }
  }

  async function resetPrefs() {
    setWeightsDraft({});
    setSoftDraft([]);
    setDealDraft([]);
    setPrefsMsg(null);
    setPrefsSaving(true);
    try {
      const next = await api<FeedPrefs>("/me/feed-preferences", {
        method: "PUT",
        body: JSON.stringify({ axis_weights: {}, soft_priority_slugs: [], dealbreaker_slugs: [] }),
      });
      setPrefs(next);
      setPrefsMsg("Сброшено к обычному среднему по осям.");
      await loadFeed(searchActive);
    } catch (e) {
      setPrefsMsg(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setPrefsSaving(false);
    }
  }

  function toggleSoft(slug: string) {
    setSoftDraft((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]
    );
  }

  function toggleDeal(slug: string) {
    setDealDraft((prev) => {
      if (prev.includes(slug)) return prev.filter((s) => s !== slug);
      if (prev.length >= 5) return prev;
      return [...prev, slug];
    });
  }

  if (!ready && !error) {
    return (
      <main className="min-h-screen flex items-center justify-center text-zinc-500">
        <span className="inline-flex items-center gap-2 text-sm">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" />
          Загрузка…
        </span>
      </main>
    );
  }

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center px-6">
        <p className="mm-error text-center max-w-sm">{error}</p>
      </main>
    );
  }

  const hasCustomPrefs =
    prefs &&
    (Object.keys(prefs.axis_weights).length > 0 ||
      prefs.soft_priority_slugs.length > 0 ||
      (prefs.dealbreaker_slugs?.length ?? 0) > 0);

  return (
    <main className="mm-page scrollbar-thin">
      <h1 className="mm-h2">Совпадения</h1>
      <p className="mm-lead mt-2 max-w-xl">
        Веса осей и «мягкие приоритеты» влияют на порядок в ленте; поиск — по тексту «о себе».
      </p>

      <div className="mt-6 flex flex-col gap-2">
        <div className="flex gap-2">
          <input
            type="search"
            className="mm-input-search"
            placeholder="Слова в «о себе»…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") setSearchActive(search);
            }}
          />
          <button type="button" className="mm-btn-secondary shrink-0 px-5" onClick={() => setSearchActive(search)}>
            Найти
          </button>
        </div>
        {searchActive ? (
          <p className="text-xs text-zinc-500">
            Фильтр: «{searchActive}»{" "}
            <button type="button" className="mm-btn-ghost p-0" onClick={() => { setSearch(""); setSearchActive(""); }}>
              сбросить
            </button>
          </p>
        ) : null}
      </div>

      <button
        type="button"
        className="mt-5 w-full text-left mm-card-static py-4 hover:border-emerald-500/20 transition-colors"
        onClick={() => setPrefsOpen(!prefsOpen)}
      >
        <span className="text-zinc-300">Настройки ленты (веса осей)</span>
        {hasCustomPrefs ? (
          <span className="block text-xs text-emerald-500/90 mt-1">активны свои правила сортировки</span>
        ) : (
          <span className="block text-xs text-zinc-600 mt-1">по умолчанию — среднее по всем осям</span>
        )}
      </button>

      {prefsOpen && prefs ? (
        <section className="mt-3 mm-panel space-y-4">
          <p className="text-xs text-zinc-500">
            Вес 0 = не учитывать ось в скоре; 1 = как обычно; до 3 = важнее. «Мягкий приоритет» —
            штраф к скору при расхождении. «Dealbreaker» — если по оси сильное расхождение, совместимость
            сильно ограничивается (как «обязательное совпадение» в духе OkCupid).
          </p>
          <ul className="space-y-3">
            {prefs.available_axes.map((ax) => (
              <li key={ax.slug} className="flex flex-col gap-1">
                <div className="flex justify-between text-sm">
                  <span>{ax.name}</span>
                  <span className="text-zinc-500 font-mono">
                    {weightsDraft[ax.slug] ?? "—"}
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={3}
                  step={0.5}
                  value={weightsDraft[ax.slug] ?? 1}
                  onChange={(e) =>
                    setWeightsDraft((w) => ({ ...w, [ax.slug]: Number(e.target.value) }))
                  }
                  className="w-full accent-emerald-500"
                />
              </li>
            ))}
          </ul>
          <div>
            <p className="text-xs text-zinc-500 mb-2">Мягко важные оси (штраф при расхождении)</p>
            <div className="flex flex-wrap gap-2">
              {prefs.available_axes.map((ax) => (
                <button
                  key={ax.slug}
                  type="button"
                  onClick={() => toggleSoft(ax.slug)}
                  className={`rounded-full px-3 py-1 text-xs border ${
                    softDraft.includes(ax.slug)
                      ? "border-amber-500/60 bg-amber-500/10 text-amber-200"
                      : "border-zinc-700 text-zinc-400"
                  }`}
                >
                  {ax.name}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs text-zinc-500 mb-2">Dealbreaker-оси (до 5)</p>
            <div className="flex flex-wrap gap-2">
              {prefs.available_axes.map((ax) => (
                <button
                  key={`d-${ax.slug}`}
                  type="button"
                  onClick={() => toggleDeal(ax.slug)}
                  className={`rounded-full px-3 py-1 text-xs border ${
                    dealDraft.includes(ax.slug)
                      ? "border-red-500/60 bg-red-500/10 text-red-200"
                      : "border-zinc-700 text-zinc-400"
                  }`}
                >
                  {ax.name}
                </button>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={prefsSaving}
              onClick={() => void savePrefs()}
              className="mm-btn-primary flex-1 py-2.5 text-sm disabled:opacity-50"
            >
              {prefsSaving ? "…" : "Сохранить"}
            </button>
            <button
              type="button"
              disabled={prefsSaving}
              onClick={() => void resetPrefs()}
              className="mm-btn-secondary px-4 py-2.5 text-sm"
            >
              Сбросить
            </button>
          </div>
          {prefsMsg ? <p className="text-xs text-zinc-500">{prefsMsg}</p> : null}
        </section>
      ) : null}

      {likeInbox.length ? (
        <section className="mt-8 rounded-2xl border border-emerald-500/25 bg-gradient-to-br from-emerald-950/40 to-zinc-900/30 p-5 shadow-mm-card">
          <p className="text-sm text-emerald-200 font-semibold">Вам поставили лайк</p>
          <p className="text-xs text-zinc-500 mt-1">
            Открой профиль и лайкни в ответ — при взаимности появится кнопка «Начать чат».
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {likeInbox.slice(0, 8).map((x) => (
              <Link
                key={x.from_user_id}
                href={`/users/${x.from_user_id}`}
                className="rounded-full border border-zinc-700/80 bg-zinc-900/70 px-3 py-1.5 text-xs hover:border-emerald-500/35 hover:bg-zinc-800/80 transition-colors"
              >
                {x.from_display_name || `Пользователь #${x.from_user_id}`}
              </Link>
            ))}
            {likeInbox.length > 8 ? (
              <span className="text-xs text-zinc-600 px-2 py-1">и ещё {likeInbox.length - 8}</span>
            ) : null}
          </div>
        </section>
      ) : null}

      <div className="mt-8 flex flex-col gap-6">
        {cards.map((c) => (
          <Link
            key={c.user_id}
            href={`/users/${c.user_id}`}
            className="block mm-card cursor-pointer"
            aria-label={`${c.display_name}, совпадение ${c.match_percent}%`}
          >
            <div className="flex justify-between items-start gap-4">
              <div>
                <p className="text-zinc-500 text-xs uppercase tracking-wide">Совпадение</p>
                <p className="text-4xl font-bold text-emerald-400">{c.match_percent}%</p>
                {c.weighted_used ? (
                  <p className="text-xs text-zinc-500 mt-1">
                    базовое среднее: {c.base_match_percent}%
                  </p>
                ) : null}
              </div>
              <FeedAvatar name={c.display_name} url={c.avatar_url} />
            </div>
            <p className="mt-4 font-medium">{c.display_name}</p>

            {c.keyword_hit ? (
              <p className="mt-3 text-xs text-zinc-500">
                Совпадение по поиску ({c.keyword_hit.field}):{" "}
                <span className="text-zinc-300">{c.keyword_hit.snippet}</span>
              </p>
            ) : null}

            {c.dealbreaker_hit ? (
              <p className="mt-2 text-xs text-red-400/90">
                Сработал dealbreaker: по важной для вас оси сильное расхождение — совместимость
                ограничена.
              </p>
            ) : null}

            {c.soft_penalty_notes.length ? (
              <ul className="mt-2 text-xs text-amber-500/90 space-y-0.5">
                {c.soft_penalty_notes.map((n) => (
                  <li key={n}>⚠ {n}</li>
                ))}
              </ul>
            ) : null}

            <ul className="mt-3 space-y-1 text-sm text-zinc-300">
              {c.agreements.map((x) => (
                <li key={x.slug + x.detail} className="flex gap-2">
                  <span className="text-emerald-500">✓</span>
                  {x.detail}
                </li>
              ))}
              {c.differences.map((x) => (
                <li key={x.slug + x.detail} className="flex gap-2">
                  <span className="text-amber-500">≠</span>
                  {x.detail}
                </li>
              ))}
            </ul>
          </Link>
        ))}
        {!cards.length && (
          <p className="mm-empty">
            {searchActive.trim() ? (
              <>
                Никого по заданным условиям — ослабь поиск или{" "}
                <button type="button" className="underline text-emerald-500/90" onClick={() => { setSearch(""); setSearchActive(""); }}>
                  сбрось фильтр «о себе»
                </button>
                .
              </>
            ) : (
              <>
                <span className="block text-zinc-300">
                  Лента <strong>не отбирает</strong> людей по схожести профиля — в неё попадают{" "}
                  <strong>все остальные</strong> пользователи в той же базе, что и API. Пустой список значит: в этой
                  базе для вашего аккаунта нет других строк пользователей (или мешает поиск выше).
                </span>
                {feedMeta ? (
                  <span className="block mt-3 text-sm text-zinc-400">
                    Этот API подключён к <strong className="text-zinc-200">{feedMeta.api_database}</strong>. В нём
                    сейчас <strong className="text-zinc-200">{feedMeta.other_users_total}</strong> других
                    пользователей
                    {feedMeta.visible_not_blocked !== feedMeta.other_users_total
                      ? ` (${feedMeta.visible_not_blocked} без блокировок)`
                      : ""}
                    . Если <strong>0</strong> — в этой базе кроме вас никого нет (часто два разных uvicorn или{" "}
                    <code className="text-zinc-500">NEXT_PUBLIC_API_URL</code> не на тот порт). Для сида: тот же{" "}
                    <code className="text-zinc-500">DATABASE_URL</code>, что у процесса API.
                  </span>
                ) : null}
              </>
            )}
          </p>
        )}
      </div>
      <BottomNav />
    </main>
  );
}
