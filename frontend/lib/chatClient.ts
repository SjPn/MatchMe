/** Near bottom of a scroll container (for “read only when user saw latest”). */
export function isScrollNearBottom(el: HTMLElement, thresholdPx = 96): boolean {
  const gap = el.scrollHeight - el.scrollTop - el.clientHeight;
  return gap <= thresholdPx;
}

export type ChatNotificationOptions = {
  /** Same tag replaces the previous notification (one banner per chat). */
  tag?: string;
};

/** Short two-tone ping — best-effort (mobile may mute until user interacted with the page once). */
export function playSoftMessagePing(): void {
  try {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();

    function blip(freq: number, startSec: number, peak: number) {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = "sine";
      o.frequency.value = freq;
      g.gain.value = 0.0001;
      o.connect(g);
      g.connect(ctx.destination);
      const t0 = ctx.currentTime + startSec;
      g.gain.exponentialRampToValueAtTime(peak, t0 + 0.018);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.11);
      o.start(t0);
      o.stop(t0 + 0.12);
    }

    blip(784, 0, 0.085);
    blip(1047, 0.13, 0.065);

    window.setTimeout(() => {
      try {
        void ctx.close();
      } catch {
        /* ignore */
      }
    }, 380);
  } catch {
    /* ignore */
  }
}

/**
 * System banner + default notification sound (when `silent` is not set).
 * On Android Chrome / installed PWA this behaves similarly to Telegram heads-up when the tab is in background.
 * On iOS: works best when the site is installed “На экран Домой” and notifications are allowed (Safari 16.4+).
 */
export function showChatNotificationIfAllowed(
  title: string,
  body: string,
  options?: ChatNotificationOptions
): void {
  if (typeof window === "undefined" || typeof Notification === "undefined") return;
  if (document.visibilityState === "visible") return;
  if (Notification.permission !== "granted") return;
  try {
    new Notification(title, {
      body: body.trim().slice(0, 160) || "Новое сообщение",
      tag: options?.tag,
    });
    try {
      if (typeof navigator !== "undefined" && typeof navigator.vibrate === "function") {
        navigator.vibrate([18, 55, 22]);
      }
    } catch {
      /* ignore */
    }
  } catch {
    /* ignore */
  }
}

export function requestNotificationPermission(): Promise<NotificationPermission> {
  if (typeof window === "undefined" || typeof Notification === "undefined") {
    return Promise.resolve("denied");
  }
  if (Notification.permission !== "default") return Promise.resolve(Notification.permission);
  return Notification.requestPermission();
}
