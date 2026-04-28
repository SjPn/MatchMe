import { useEffect, useRef } from "react";

export type NearBottomFn = (el: HTMLElement) => boolean;

export type PollingOptions<TMsg> = {
  /** Enable polling loop */
  enabled: boolean;
  /** Poll interval in ms */
  intervalMs: number;
  /** Scroll container ref */
  scrollRef: React.RefObject<HTMLElement | null>;
  /** True if tab is hidden */
  isTabHidden: () => boolean;
  /** Near-bottom detector */
  isNearBottom: NearBottomFn;
  /** Read current message list */
  getMessages: () => TMsg[];
  /** Extract numeric id for "after_id" and mark-read */
  getId: (m: TMsg) => number;
  /** Merge function (must preserve order) */
  merge: (prev: TMsg[], incoming: TMsg[]) => TMsg[];
  /** Commit new list */
  setMessages: (updater: (prev: TMsg[]) => TMsg[]) => void;
  /** Fetch newer messages after id (exclusive) */
  fetchNewer: (afterId: number) => Promise<TMsg[]>;
  /** Optional extra poll action (typing indicators etc.) */
  fetchSidecar?: () => Promise<void>;
  /**
   * Called when new messages arrive.
   * Provides: whether user was near bottom, and the newest batch.
   */
  onIncoming?: (args: { wasNearBottom: boolean; newer: TMsg[] }) => void;
  /** Mark as read when near bottom (called with last message id) */
  markRead?: (lastMessageId: number) => void;
};

/**
 * Shared polling + auto-scroll behavior for chat pages.
 * Keeps an internal lastIdRef (based on merged message list).
 */
export function useChatPolling<TMsg>(opts: PollingOptions<TMsg>) {
  const lastIdRef = useRef(0);
  const atBottomRef = useRef(true);
  const lastMarkedReadId = useRef(0);

  // Keep refs in sync with external message list
  useEffect(() => {
    const list = opts.getMessages();
    const last = list.length ? opts.getId(list[list.length - 1]) : 0;
    if (last > lastIdRef.current) lastIdRef.current = last;
  }, [opts]);

  function tryMarkReadNow() {
    if (!opts.markRead) return;
    if (opts.isTabHidden()) return;
    const box = opts.scrollRef.current;
    if (!box || !opts.isNearBottom(box)) return;
    const list = opts.getMessages();
    const lastId = list.length ? opts.getId(list[list.length - 1]) : 0;
    if (lastId <= 0 || lastId <= lastMarkedReadId.current) return;
    lastMarkedReadId.current = lastId;
    opts.markRead(lastId);
  }

  function onScroll() {
    const box = opts.scrollRef.current;
    if (!box) return;
    atBottomRef.current = opts.isNearBottom(box);
    tryMarkReadNow();
  }

  useEffect(() => {
    // reset when disabled/enabled toggles
    if (!opts.enabled) return;
    lastMarkedReadId.current = 0;
    atBottomRef.current = true;
    // do not reset lastIdRef; it is derived from current list
  }, [opts.enabled]);

  useEffect(() => {
    if (!opts.enabled) return;

    let cancelled = false;
    async function tick() {
      if (cancelled) return;
      const box = opts.scrollRef.current;
      const wasNearBottom = box ? opts.isNearBottom(box) : true;
      try {
        await (opts.fetchSidecar?.() ?? Promise.resolve());
      } catch {
        // ignore sidecar errors
      }
      let newer: TMsg[] = [];
      try {
        newer = await opts.fetchNewer(lastIdRef.current);
      } catch {
        return;
      }
      if (!newer.length) return;

      opts.onIncoming?.({ wasNearBottom, newer });

      opts.setMessages((prev) => {
        const merged = opts.merge(prev, newer);
        const last = merged.length ? opts.getId(merged[merged.length - 1]) : 0;
        if (last > lastIdRef.current) lastIdRef.current = last;
        return merged;
      });

      if (wasNearBottom) {
        atBottomRef.current = true;
        const el = opts.scrollRef.current;
        if (el) {
          // Defer to let React commit DOM changes
          requestAnimationFrame(() => {
            try {
              el.scrollTop = el.scrollHeight;
            } catch {
              /* ignore */
            }
            tryMarkReadNow();
          });
        }
      } else {
        atBottomRef.current = false;
      }
    }

    void tick();
    const id = window.setInterval(() => void tick(), opts.intervalMs);
    document.addEventListener("visibilitychange", tick);
    return () => {
      cancelled = true;
      window.clearInterval(id);
      document.removeEventListener("visibilitychange", tick);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opts.enabled, opts.intervalMs]);

  return {
    lastIdRef,
    atBottomRef,
    onScroll,
    tryMarkReadNow,
  };
}

