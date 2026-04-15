/**
 * Если NEXT_PUBLIC_API_URL не задан — ходим на тот же origin в /api/*,
 * Next.js проксирует на бэкенд (next.config.mjs). Так меньше «Failed to fetch», когда
 * фронт открыт как localhost, а до :8000 браузер не достучался.
 */
export function apiUrl(path: string): string {
  const pathNorm = path.startsWith("/") ? path : `/${path}`;
  const direct = process.env.NEXT_PUBLIC_API_URL?.trim();
  if (direct) {
    return `${direct.replace(/\/$/, "")}${pathNorm}`;
  }
  return `/api${pathNorm}`;
}

const TOKEN_KEY = "matchme_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

function isLocalDev(): boolean {
  if (typeof window === "undefined") return false;
  const h = window.location.hostname;
  return h === "localhost" || h === "127.0.0.1";
}

/** 502/503 от Render: бэкенд «спит» или прокси не дождался — имеет смысл повторить безопасный запрос. */
function isGatewayRetryable(status: number): boolean {
  return status === 502 || status === 503 || status === 504;
}

function serverErrorUserHint(status: number, bodyPreview: string): string {
  if (!isLocalDev() && isGatewayRetryable(status)) {
    return (
      `Сервер временно недоступен (${status}). Часто это «пробуждение» API после простоя на бесплатном хостинге — ` +
      `подождите 10–30 с и обновите страницу. Фрагмент ответа: ${bodyPreview.slice(0, 200)}`
    );
  }
  return `Сервер вернул ошибку (${status}). Открой терминал с uvicorn — там traceback. Текст ответа: ${bodyPreview.slice(0, 200)}`;
}

function noConnectionHint(): string {
  if (!isLocalDev()) {
    return (
      "Нет связи с API. Проверьте интернет и что сервис бэкенда запущен " +
      "(на Render у фронтенда должна быть задана переменная BACKEND_URL на URL API)."
    );
  }
  return (
    "Нет связи с API. Запусти бэкенд в отдельном терминале:\n" +
    "cd backend → .\\.venv\\Scripts\\Activate.ps1 → $env:PYTHONPATH=\".\" → uvicorn app.main:app --reload --port 8000"
  );
}

async function sleep(ms: number): Promise<void> {
  await new Promise((r) => setTimeout(r, ms));
}

/** Повторы для GET/HEAD при 502/503/504 и сетевых сбоях (cold start на Render и т.п.). */
async function fetchWithGatewayRetries(url: string, init: RequestInit): Promise<Response> {
  const method = (init.method || "GET").toUpperCase();
  const allowGatewayRetry = method === "GET" || method === "HEAD";
  const maxAttempts = allowGatewayRetry ? 4 : 1;
  const backoffMs = [0, 1200, 3500, 8000];

  let res: Response | undefined;

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    if (backoffMs[attempt] > 0) await sleep(backoffMs[attempt]);
    try {
      res = await fetch(url, init);
    } catch (e) {
      if (allowGatewayRetry && attempt < maxAttempts - 1) continue;
      throw new Error(e instanceof Error && e.message === "Failed to fetch" ? noConnectionHint() : String(e));
    }
    if (allowGatewayRetry && res && isGatewayRetryable(res.status) && attempt < maxAttempts - 1) {
      continue;
    }
    break;
  }

  if (!res) throw new Error(noConnectionHint());
  return res;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const t = getToken();
  if (t) headers.set("Authorization", `Bearer ${t}`);

  const res = await fetchWithGatewayRetries(apiUrl(path), { ...init, headers });

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      throw new Error(res.status >= 500 ? serverErrorUserHint(res.status, text) : text.slice(0, 300));
    }
  }
  if (!res.ok) {
    const d = data as { detail?: unknown } | null;
    const detail = d?.detail ?? res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data as T;
}

/** GET с If-None-Match: 304 — без тела, клиент сохраняет предыдущие данные. */
export type ApiEtagResult<T> =
  | { notModified: true; etag: string | null }
  | { notModified: false; data: T; etag: string | null };

export async function apiJsonWithEtag<T>(path: string, etagPrevious: string | null): Promise<ApiEtagResult<T>> {
  const headers = new Headers();
  headers.set("Accept", "application/json");
  const t = getToken();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  if (etagPrevious) headers.set("If-None-Match", etagPrevious);

  const res = await fetchWithGatewayRetries(apiUrl(path), { headers });

  const etag = res.headers.get("ETag");

  if (res.status === 304) {
    return { notModified: true, etag: etag ?? etagPrevious };
  }

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      throw new Error(res.status >= 500 ? serverErrorUserHint(res.status, text) : text.slice(0, 300));
    }
  }
  if (!res.ok) {
    const d = data as { detail?: unknown } | null;
    const detail = d?.detail ?? res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return { notModified: false, data: data as T, etag };
}

/** multipart/form-data (файлы в чате). Не выставляем Content-Type — boundary задаст браузер. */
export async function postFormData<T>(path: string, form: FormData): Promise<T> {
  const headers = new Headers();
  const t = getToken();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  const res = await fetch(apiUrl(path), { method: "POST", headers, body: form });
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      throw new Error(text.slice(0, 300));
    }
  }
  if (!res.ok) {
    const d = data as { detail?: unknown } | null;
    const detail = d?.detail ?? res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data as T;
}

export async function downloadBlob(path: string): Promise<Blob> {
  const headers = new Headers();
  const t = getToken();
  if (t) headers.set("Authorization", `Bearer ${t}`);
  const res = await fetch(apiUrl(path), { headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text.slice(0, 200) || res.statusText);
  }
  return res.blob();
}
