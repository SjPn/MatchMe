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

let _warnedDirectApiUrl = false;

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const t = getToken();
  if (t) headers.set("Authorization", `Bearer ${t}`);

  let res: Response;
  try {
    res = await fetch(apiUrl(path), { ...init, headers });
  } catch (e) {
    const hint =
      "Нет связи с API. Запусти бэкенд в отдельном терминале:\n" +
      "cd backend → .\\.venv\\Scripts\\Activate.ps1 → $env:PYTHONPATH=\".\" → uvicorn app.main:app --reload --port 8000";
    throw new Error(e instanceof Error && e.message === "Failed to fetch" ? hint : String(e));
  }

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text) as unknown;
    } catch {
      throw new Error(
        res.status >= 500
          ? `Сервер вернул ошибку (${res.status}). Открой терминал с uvicorn — там traceback. Текст ответа: ${text.slice(0, 200)}`
          : text.slice(0, 300)
      );
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

  let res: Response;
  try {
    res = await fetch(apiUrl(path), { headers });
  } catch (e) {
    const hint =
      "Нет связи с API. Запусти бэкенд в отдельном терминале:\n" +
      "cd backend → .\\.venv\\Scripts\\Activate.ps1 → $env:PYTHONPATH=\".\" → uvicorn app.main:app --reload --port 8000";
    throw new Error(e instanceof Error && e.message === "Failed to fetch" ? hint : String(e));
  }

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
      throw new Error(
        res.status >= 500
          ? `Сервер вернул ошибку (${res.status}). Открой терминал с uvicorn — там traceback.`
          : text.slice(0, 300)
      );
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
