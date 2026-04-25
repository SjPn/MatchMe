"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { api, avatarPublicSrc, getToken, postFormData, setToken } from "@/lib/api";

type Summary = {
  display_name: string;
  onboarding_step: string;
  completion_percent: number;
  onboarding_plus_total?: number;
  onboarding_plus_answered?: number;
  badges?: string[];
  mind_lines?: string[];
  about_me: string | null;
  privacy: {
    answers_visible_to_others: boolean;
    others_see_axis_summary_only: boolean;
    hint: string;
  };
  axes: {
    slug: string;
    name: string;
    score: number;
    left_label: string;
    right_label: string;
    lean: string;
  }[];
};

type Me = {
  display_name: string;
  avatar_url: string | null;
  about_me?: string | null;
  identity_verified?: boolean;
};

export default function SummaryPage() {
  const router = useRouter();
  const [data, setData] = useState<Summary | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [avatarUrl, setAvatarUrl] = useState("");
  const [aboutMe, setAboutMe] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [verifyBusy, setVerifyBusy] = useState(false);
  const [avatarBusy, setAvatarBusy] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    (async () => {
      try {
        const [s, m] = await Promise.all([
          api<Summary>("/me/summary"),
          api<Me>("/auth/me"),
        ]);
        if (s.onboarding_step !== "test_completed") {
          router.replace("/test");
          return;
        }
        setData(s);
        setMe(m);
        setAvatarUrl(m.avatar_url ?? "");
        setAboutMe((m.about_me ?? s.about_me) ?? "");
      } catch (e) {
        setError(e instanceof Error ? e.message : "Ошибка");
      }
    })();
  }, [router]);

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    setSaveMsg(null);
    setSaving(true);
    try {
      const next = await api<Me>("/me/profile", {
        method: "PATCH",
        body: JSON.stringify({
          avatar_url: avatarUrl.trim() || null,
          about_me: aboutMe.trim() || null,
        }),
      });
      setMe(next);
      const s2 = await api<Summary>("/me/summary");
      setData(s2);
      setSaveMsg("Сохранено");
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : "Ошибка");
    } finally {
      setSaving(false);
    }
  }

  async function onVerificationFile(f: File | null) {
    if (!f) return;
    setSaveMsg(null);
    setVerifyBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const next = await postFormData<Me>("/me/verification-photo", fd);
      setMe(next);
      setSaveMsg("Фото принято — в профиле для других будет отметка доверия.");
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : "Ошибка загрузки");
    } finally {
      setVerifyBusy(false);
    }
  }

  async function onAvatarFile(f: File | null) {
    if (!f) return;
    setSaveMsg(null);
    setAvatarBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", f);
      const next = await postFormData<Me>("/me/avatar", fd);
      setMe(next);
      setAvatarUrl(next.avatar_url ?? "");
      setSaveMsg("Аватар обновлён.");
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : "Ошибка загрузки");
    } finally {
      setAvatarBusy(false);
    }
  }

  if (error) {
    return (
      <main className="min-h-screen flex flex-col items-center justify-center px-6 text-red-400">
        <p className="mm-error text-center max-w-sm">{error}</p>
      </main>
    );
  }

  if (!data) {
    return (
      <main className="min-h-screen flex items-center justify-center text-zinc-500">
        <span className="inline-flex items-center gap-2 text-sm">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-500/30 border-t-emerald-400" aria-hidden />
          Считаем профиль…
        </span>
      </main>
    );
  }

  return (
    <main className="mm-page scrollbar-thin">
      <div className="flex justify-end">
        <button
          type="button"
          className="text-sm text-zinc-500 hover:text-zinc-300 underline-offset-2 hover:underline"
          onClick={() => {
            setToken(null);
            router.replace("/login");
          }}
        >
          Выйти из аккаунта
        </button>
      </div>
      <p className="text-emerald-400/95 text-sm font-medium mt-2">Твой профиль в MatchMe</p>
      <h1 className="mm-h1 mt-3">Привет, {data.display_name}</h1>
      <p className="mm-lead mt-2 max-w-xl">
        Ниже — срез по осям (0–1) на основе ответов. Это не клиническая диагностика, а ориентир для совпадений.
      </p>

      <div className="mt-4 mm-card-static px-4 py-3 text-xs text-zinc-400 leading-relaxed">
        <p className="text-zinc-200 font-medium text-sm mb-1">Приватность ответов</p>
        <p>{data.privacy.hint}</p>
      </div>

      {me ? (
        <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-900/40 px-4 py-3">
          <p className="text-sm text-zinc-300">Доверие к профилю</p>
          <p className="text-xs text-zinc-500 mt-1">
            Загрузите селфи (JPG/PNG/WebP, до 5 МБ) — в MVP после загрузки ставится отметка для других
            пользователей.
          </p>
          {me.identity_verified ? (
            <p className="text-xs text-sky-400 mt-2">✓ Отметка активна</p>
          ) : (
            <>
              <input
                id="summary-verify-photo"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="sr-only"
                disabled={verifyBusy}
                onChange={(e) => void onVerificationFile(e.target.files?.[0] ?? null)}
              />
              <label
                htmlFor="summary-verify-photo"
                className="mt-2 inline-block text-xs text-emerald-400 cursor-pointer underline-offset-2 hover:underline"
              >
                {verifyBusy ? "Загрузка…" : "Выбрать фото"}
              </label>
            </>
          )}
        </div>
      ) : null}

      {me ? (
        <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-900/30 px-4 py-3">
          <p className="text-sm text-zinc-300">Аватар</p>
          <p className="text-xs text-zinc-500 mt-1">
            Это картинка, которая показывается в ленте и на вашей странице. Не путать с селфи для отметки доверия.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-3">
            {me.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={avatarPublicSrc(me.avatar_url)}
                alt="Ваш аватар"
                className="h-14 w-14 rounded-full object-cover border border-emerald-500/20"
              />
            ) : (
              <span className="mm-badge">нет аватара</span>
            )}
            <input
              id="summary-avatar-file"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              disabled={avatarBusy}
              onChange={(e) => void onAvatarFile(e.target.files?.[0] ?? null)}
            />
            <label
              htmlFor="summary-avatar-file"
              className="text-xs text-emerald-400 cursor-pointer underline-offset-2 hover:underline"
            >
              {avatarBusy ? "Загрузка…" : "Сменить аватар"}
            </label>
            {me.avatar_url ? (
              <button
                type="button"
                className="text-xs text-zinc-500 hover:text-zinc-300 underline-offset-2 hover:underline"
                disabled={avatarBusy}
                onClick={async () => {
                  setAvatarBusy(true);
                  setSaveMsg(null);
                  try {
                    const next = await api<Me>("/me/avatar", { method: "DELETE" });
                    setMe(next);
                    setAvatarUrl(next.avatar_url ?? "");
                    setSaveMsg("Аватар удалён.");
                  } catch (err) {
                    setSaveMsg(err instanceof Error ? err.message : "Ошибка");
                  } finally {
                    setAvatarBusy(false);
                  }
                }}
              >
                Удалить
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {(data.badges ?? []).length ? (
        <div className="mt-6 flex flex-wrap gap-2">
          {(data.badges ?? []).includes("transparent_axes") ? (
            <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-300">
              Прозрачный профиль по осям
            </span>
          ) : null}
          {(data.badges ?? []).includes("about_me") ? (
            <span className="rounded-full border border-sky-500/40 bg-sky-500/10 px-3 py-1 text-xs text-sky-200">
              Есть «о себе»
            </span>
          ) : null}
        </div>
      ) : null}

      {(data.mind_lines ?? []).length ? (
        <section className="mt-6 mm-panel" aria-labelledby="mind-lines-heading">
          <h2 id="mind-lines-heading" className="text-xs uppercase tracking-wide text-zinc-500 mb-2">
            Как я думаю
          </h2>
          <ul className="space-y-1 text-sm text-zinc-300">
            {(data.mind_lines ?? []).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {me && (
        <form
          onSubmit={(e) => void saveProfile(e)}
          className="mt-8 mm-card-static space-y-4"
          aria-labelledby="profile-form-heading"
        >
          <h2 id="profile-form-heading" className="text-sm font-medium text-zinc-200">
            Профиль
          </h2>
          {(data.onboarding_plus_total ?? 0) > 0 &&
          (data.onboarding_plus_answered ?? 0) < (data.onboarding_plus_total ?? 0) ? (
            <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/5 px-3 py-3 space-y-2">
              <p className="text-xs text-zinc-400 leading-relaxed">
                Доступен второй блок из 10 вопросов — он уточнит оси профиля (справедливость, автономия,
                эмоции vs логика и др.).
              </p>
              <Link
                href="/test?pack=onboarding_plus"
                className="inline-flex items-center justify-center rounded-lg bg-emerald-500 text-zinc-950 text-sm font-medium px-4 py-2.5 w-full sm:w-auto"
              >
                Продолжить опрос
              </Link>
            </div>
          ) : null}
          {(data.onboarding_plus_total ?? 0) > 0 &&
          (data.onboarding_plus_answered ?? 0) >= (data.onboarding_plus_total ?? 0) ? (
            <p className="text-xs text-zinc-500">
              Дополнительный блок из 10 вопросов пройден — оси профиля обновлены с учётом этих ответов.
            </p>
          ) : null}
          <div className="rounded-lg border border-zinc-800 bg-zinc-950/20 px-3 py-2">
            <p className="text-xs text-zinc-400">
              Android-приложение:{" "}
              <a
                href="/downloads/MatchMe.apk"
                download
                className="text-emerald-400 underline underline-offset-2 hover:text-emerald-300"
              >
                скачать APK
              </a>
            </p>
            <p className="text-[11px] text-zinc-600 mt-1 leading-relaxed">
              Установка: открой файл на Android и разреши установку из неизвестных источников для браузера/файлового
              менеджера.
            </p>
          </div>
          <div>
            <label htmlFor="summary-about" className="text-sm text-zinc-400 block">
              Несколько слов о себе
            </label>
            <p className="text-xs text-zinc-600 mt-1">
              Поиск в ленте учитывает этот текст; оси по-прежнему главный сигнал совместимости.
            </p>
            <textarea
              id="summary-about"
              className="mm-input mt-2 min-h-[88px]"
              value={aboutMe}
              onChange={(e) => setAboutMe(e.target.value)}
              placeholder="Интересы, стиль мышления, что важно в людях…"
              maxLength={4000}
            />
          </div>
          <div>
            <label htmlFor="summary-avatar-url" className="text-sm text-zinc-400 block">
              Аватар в ленте
            </label>
            <p className="text-xs text-zinc-600 mt-1">
              Прямая ссылка (https…). Если вы загрузили аватар выше — это поле можно оставить пустым.
            </p>
            <input
              id="summary-avatar-url"
              type="url"
              className="mm-input mt-2"
              value={avatarUrl}
              onChange={(e) => setAvatarUrl(e.target.value)}
              placeholder="https://…"
              autoComplete="off"
            />
          </div>
          <button type="submit" disabled={saving} className="mm-btn-secondary disabled:opacity-50">
            {saving ? "…" : "Сохранить"}
          </button>
          {saveMsg ? <p className="text-xs text-zinc-500">{saveMsg}</p> : null}
        </form>
      )}
      <ul className="mt-8 space-y-3" aria-label="Срез по осям ценностей">
        {data.axes.map((a) => {
          const pct = Math.round(a.score * 100);
          return (
            <li key={a.slug} className="mm-card-static px-4 py-3 space-y-2">
              <div className="flex justify-between items-start gap-4">
                <div className="min-w-0">
                  <h3 className="text-sm font-medium text-zinc-200">{a.name}</h3>
                  <p className="text-xs text-zinc-500 mt-0.5">{a.lean}</p>
                </div>
                <span className="text-emerald-400 font-mono text-xs shrink-0">{pct}%</span>
              </div>
              <div className="relative h-2 rounded-full bg-zinc-800 overflow-hidden" aria-hidden>
                <div
                  className="absolute inset-y-0 left-0 bg-emerald-500/35"
                  style={{ width: `${pct}%` }}
                />
                <div
                  className="absolute -top-1 h-4 w-1.5 rounded bg-emerald-400"
                  style={{ left: `calc(${pct}% - 3px)` }}
                />
              </div>
              <div className="flex justify-between text-[10px] text-zinc-500" aria-hidden>
                <span className="max-w-[48%] truncate">{a.left_label}</span>
                <span className="max-w-[48%] truncate text-right">{a.right_label}</span>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-6 text-xs text-zinc-500">
        Заполненность онбординга:{" "}
        <span className="text-zinc-300 font-medium text-sm">{data.completion_percent}%</span>
      </p>
      <Link href="/feed" className="mm-btn-primary mt-10 block w-full text-center py-3.5">
        Показать людей, похожих на меня
      </Link>
      <BottomNav />
    </main>
  );
}
