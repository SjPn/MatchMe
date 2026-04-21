/** Near bottom of a scroll container (for “read only when user saw latest”). */
export function isScrollNearBottom(el: HTMLElement, thresholdPx = 96): boolean {
  const gap = el.scrollHeight - el.scrollTop - el.clientHeight;
  return gap <= thresholdPx;
}

/** One soft ping when the tab is in background (best-effort; may fail without prior user gesture). */
export function playSoftMessagePing(): void {
  try {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const o = ctx.createOscillator();
    const g = ctx.createGain();
    o.type = "sine";
    o.frequency.value = 880;
    g.gain.value = 0.0001;
    o.connect(g);
    g.connect(ctx.destination);
    const t0 = ctx.currentTime;
    g.gain.exponentialRampToValueAtTime(0.08, t0 + 0.02);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + 0.12);
    o.start(t0);
    o.stop(t0 + 0.13);
    o.onended = () => void ctx.close();
  } catch {
    /* ignore */
  }
}

export function showChatNotificationIfAllowed(title: string, body: string): void {
  if (typeof window === "undefined" || typeof Notification === "undefined") return;
  if (document.visibilityState === "visible") return;
  if (Notification.permission !== "granted") return;
  try {
    new Notification(title, {
      body: body.trim().slice(0, 160) || "Новое сообщение",
      silent: true,
    });
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
