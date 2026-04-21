"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { api, getToken } from "@/lib/api";

type DirectRow = {
  kind?: "direct";
  conversation_id: number;
  other_user_id: number;
  other_display_name: string;
  last_activity_at?: string | null;
  unread_count?: number;
};

type GroupRow = {
  kind: "group";
  group_room_id: number;
  title: string;
  member_count: number;
  last_activity_at?: string | null;
  unread_count?: number;
};

type Row = DirectRow | GroupRow;

type JoinOut = {
  status: string;
  room_id?: number | null;
  message?: string | null;
  eligible_peers?: number | null;
  min_members?: number | null;
};

function UnreadBadge({ n }: { n: number }) {
  if (n <= 0) return null;
  const label = n > 99 ? "99+" : String(n);
  return (
    <span
      className="min-w-[1.25rem] h-5 px-1.5 rounded-full bg-red-500 text-[11px] font-semibold text-white flex items-center justify-center tabular-nums"
      aria-label={`Непрочитанных сообщений: ${n}`}
    >
      {label}
    </span>
  );
}

export default function ConversationsPage() {
  const router = useRouter();
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [joinMsg, setJoinMsg] = useState<string | null>(null);
  const [joining, setJoining] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }

    let cancelled = false;

    async function load() {
      try {
        const data = await api<Row[]>("/conversations");
        if (!cancelled) {
          setRows(data);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Ошибка");
        }
      }
    }

    void load();
    const id = window.setInterval(() => {
      if (typeof document !== "undefined" && document.hidden) return;
      void load();
    }, 5000);

    function onVisibility() {
      if (!document.hidden) void load();
    }
    document.addEventListener("visibilitychange", onVisibility);

    return () => {
      cancelled = true;
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [router]);

  async function joinGroup() {
    setJoining(true);
    setJoinMsg(null);
    try {
      const out = await api<JoinOut>("/group-rooms/join", { method: "POST" });
      if (out.room_id) {
        router.push(`/group-chat/${out.room_id}`);
        return;
      }
      setJoinMsg(
        out.message ??
          `Статус: ${out.status}. Подходящих по осям людей: ${out.eligible_peers ?? "?"}, нужно минимум ${out.min_members ?? "?"} для комнаты.`
      );
    } catch (e) {
      setJoinMsg(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setJoining(false);
    }
  }

  function formatTs(iso: string | null | undefined): string {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      return d.toLocaleString("ru-RU", {
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "";
    }
  }

  return (
    <main className="mm-page scrollbar-thin">
      <Link href="/feed" className="text-sm text-zinc-500 hover:text-emerald-400/90 transition-colors">
        ← Лента
      </Link>
      <h1 className="mm-h2 mt-6">Диалоги</h1>
      <p className="mm-lead mt-2 text-xs sm:text-sm">
        Личные чаты по матчам и групповые комнаты по схожим ответам (оси). В группе видны только
        псевдонимы.
      </p>

      <div className="mt-6 mm-panel space-y-3">
        <p className="text-sm font-medium text-zinc-200">Групповой чат</p>
        <p className="text-xs text-zinc-500 leading-relaxed">
          Подбор по среднему и максимуму расхождения по осям; комната создаётся, когда набирается
          достаточно близких по ответам людей.
        </p>
        <button
          type="button"
          disabled={joining}
          onClick={() => void joinGroup()}
          className="mm-btn-primary w-full py-2.5 text-sm disabled:opacity-50"
        >
          {joining ? "…" : "Найти или войти в группу"}
        </button>
        {joinMsg ? <p className="text-xs text-amber-300/90 whitespace-pre-wrap">{joinMsg}</p> : null}
      </div>

      {error ? <p className="mt-4 mm-error">{error}</p> : null}
      <ul className="mt-6 space-y-2">
        {rows.map((r) => {
          if (r.kind === "group") {
            return (
              <li key={`g-${r.group_room_id}`}>
                <Link
                  href={`/group-chat/${r.group_room_id}`}
                  className="flex justify-between gap-3 mm-card py-4 border-emerald-500/20 bg-gradient-to-br from-emerald-950/30 to-zinc-900/40 hover:border-emerald-500/35"
                >
                  <span>
                    <span className="text-[10px] text-emerald-500 uppercase tracking-wide block">
                      Группа · {r.member_count} чел.
                    </span>
                    <span className="font-medium">{r.title}</span>
                  </span>
                  <span className="flex items-center gap-2 shrink-0">
                    <UnreadBadge n={r.unread_count ?? 0} />
                    {r.last_activity_at ? (
                      <span className="text-xs text-zinc-500">{formatTs(r.last_activity_at)}</span>
                    ) : null}
                  </span>
                </Link>
              </li>
            );
          }
          return (
            <li key={`d-${r.conversation_id}`}>
              <Link
                href={`/chat/${r.conversation_id}`}
                className="flex justify-between gap-3 mm-card py-4"
              >
                <span className="font-medium">
                  <Link
                    href={`/users/${r.other_user_id}`}
                    className="hover:text-emerald-300"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {r.other_display_name || `Пользователь #${r.other_user_id}`}
                  </Link>
                </span>
                <span className="flex items-center gap-2 shrink-0">
                  <UnreadBadge n={r.unread_count ?? 0} />
                  {r.last_activity_at ? (
                    <span className="text-xs text-zinc-500">{formatTs(r.last_activity_at)}</span>
                  ) : null}
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
      {!rows.length && !error ? (
        <p className="mm-empty mt-8 text-sm">Пока нет личных матчей — группа доступна кнопкой выше.</p>
      ) : null}
      <BottomNav />
    </main>
  );
}
