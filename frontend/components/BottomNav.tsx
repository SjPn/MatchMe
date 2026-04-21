"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, getToken } from "@/lib/api";

const items: {
  href: string;
  label: string;
  match: (pathname: string) => boolean;
  icon: (active: boolean) => JSX.Element;
}[] = [
  {
    href: "/timeline",
    label: "Лента",
    match: (p) => p === "/timeline" || p.startsWith("/posts/") || p.startsWith("/threads"),
    icon: (active) => (
      <svg
        className={`h-6 w-6 ${active ? "text-emerald-400" : "text-zinc-500"}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={active ? 2 : 1.5}
        aria-hidden
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M3 12l9-9 9 9M4.5 10.5V21a.75.75 0 00.75.75h4.5V15a.75.75 0 01.75-.75h3a.75.75 0 01.75.75v6.75h4.5A.75.75 0 0019.5 21V10.5"
        />
      </svg>
    ),
  },
  {
    href: "/feed",
    label: "Люди",
    match: (p) => p === "/feed" || p.startsWith("/users/"),
    icon: (active) => (
      <svg
        className={`h-6 w-6 ${active ? "text-emerald-400" : "text-zinc-500"}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={active ? 2 : 1.5}
        aria-hidden
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z"
        />
      </svg>
    ),
  },
  {
    href: "/conversations",
    label: "Чаты",
    match: (p) => p.startsWith("/conversations") || p.startsWith("/chat") || p.startsWith("/group-chat"),
    icon: (active) => (
      <svg
        className={`h-6 w-6 ${active ? "text-emerald-400" : "text-zinc-500"}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={active ? 2 : 1.5}
        aria-hidden
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
        />
      </svg>
    ),
  },
  {
    href: "/summary",
    label: "Профиль",
    match: (p) => p.startsWith("/summary"),
    icon: (active) => (
      <svg
        className={`h-6 w-6 ${active ? "text-emerald-400" : "text-zinc-500"}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={active ? 2 : 1.5}
        aria-hidden
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
        />
      </svg>
    ),
  },
];

export function BottomNav() {
  const pathname = usePathname() || "";
  const [unreadTotal, setUnreadTotal] = useState(0);

  useEffect(() => {
    if (!getToken()) {
      setUnreadTotal(0);
      return;
    }
    let cancelled = false;

    async function tick() {
      try {
        const out = await api<{ total: number }>("/conversations/unread-count");
        if (!cancelled) setUnreadTotal(Math.max(0, Number(out.total) || 0));
      } catch {
        // keep UI stable even if API is temporarily down
      }
    }

    void tick();
    const id = window.setInterval(tick, 6000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-50 border-t border-white/[0.06] bg-zinc-950/85 px-2 pt-2 shadow-mm-nav backdrop-blur-xl supports-[backdrop-filter]:bg-zinc-950/75"
      style={{ paddingBottom: "max(0.5rem, env(safe-area-inset-bottom))" }}
      aria-label="Основное меню"
    >
      <div className="mx-auto flex max-w-shell lg:max-w-shell-wide items-stretch justify-around gap-1 pb-1">
        {items.map((item) => {
          const active = item.match(pathname);
          const showUnread = item.href === "/conversations" && unreadTotal > 0;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex min-w-0 flex-1 flex-col items-center justify-center gap-1 rounded-2xl py-2 transition-colors ${
                active
                  ? "bg-emerald-500/10 text-emerald-300"
                  : "text-zinc-500 hover:bg-zinc-800/50 hover:text-zinc-300"
              }`}
              aria-current={active ? "page" : undefined}
            >
              <span className="relative">
                {item.icon(active)}
                {showUnread ? (
                  <span
                    className="absolute -top-2 -right-3 min-w-[1.05rem] h-[1.05rem] px-1 rounded-full bg-red-500 text-[10px] leading-[1.05rem] text-white text-center font-semibold shadow"
                    aria-label={`Непрочитанные сообщения: ${unreadTotal}`}
                  >
                    {unreadTotal > 99 ? "99+" : String(unreadTotal)}
                  </span>
                ) : null}
              </span>
              <span className={`text-[11px] font-medium leading-none ${active ? "text-emerald-200" : ""}`}>
                {item.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
