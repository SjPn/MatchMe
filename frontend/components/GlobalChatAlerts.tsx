"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { api, getToken } from "@/lib/api";
import { playSoftMessagePing, showChatNotificationIfAllowed } from "@/lib/chatClient";

/**
 * When the user is not on a chat screen, poll unread totals so new messages still play sound /
 * show a system notification if the tab is in the background (other app, lock screen, etc.).
 * Open chat pages handle alerts locally via useChatPolling — we skip those routes to avoid duplicates.
 */
export function GlobalChatAlerts() {
  const pathname = usePathname() ?? "";
  const prevTotalRef = useRef<number | null>(null);

  useEffect(() => {
    if (!getToken()) return;

    const onChatSurface =
      pathname.startsWith("/chat/") || pathname.startsWith("/group-chat/");
    if (onChatSurface) {
      prevTotalRef.current = null;
      return;
    }

    let cancelled = false;

    async function tick() {
      if (cancelled || !getToken()) return;
      try {
        const data = await api<{ total?: number }>("/conversations/unread-count");
        if (cancelled) return;
        const total = typeof data.total === "number" ? data.total : 0;
        if (prevTotalRef.current !== null && total > prevTotalRef.current) {
          if (typeof document !== "undefined" && document.hidden) {
            playSoftMessagePing();
            showChatNotificationIfAllowed("MatchMe", "Новое сообщение", {
              tag: "matchme-unread-global",
            });
          }
        }
        prevTotalRef.current = total;
      } catch {
        /* offline / cold start */
      }
    }

    void tick();
    const id = window.setInterval(() => void tick(), 8000);

    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [pathname]);

  return null;
}
