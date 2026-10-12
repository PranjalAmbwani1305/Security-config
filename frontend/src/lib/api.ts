/**
 * Single API entry point for the app: base URL, auth header, token refresh and
 * error normalisation live here so pages never talk to fetch/localStorage directly.
 */
const rawUrl = import.meta.env.VITE_API_URL as string | undefined;

if (!rawUrl && !import.meta.env.DEV) {
  // Don't throw at import time: that blanks the whole app. Log loudly instead.
  console.error(
    "VITE_API_URL is not set. Set it in Vercel > Project > Settings > Environment Variables " +
      "(e.g. https://your-api.vercel.app) and redeploy.",
  );
}

export const API_URL = (rawUrl || (import.meta.env.DEV ? "http://localhost:8000" : "")).replace(/\/+$/, "");
export const GOOGLE_CLIENT_ID =
  (import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined) || undefined;

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

// Access token: memory only. Refresh token: localStorage (see note in README:
// move to an httpOnly cookie once API and frontend share a parent domain).
const REFRESH_KEY = "sentinel.refresh_token";
let accessToken: string | null = null;
let refreshInFlight: Promise<boolean> | null = null;
let onAuthLost: (() => void) | null = null;

export const tokens = {
  set(access: string, refresh: string) {
    accessToken = access;
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    accessToken = null;
    localStorage.removeItem(REFRESH_KEY);
  },
  hasRefresh: () => !!localStorage.getItem(REFRESH_KEY),
};

export function setAuthLostHandler(handler: (() => void) | null) {
  onAuthLost = handler;
}

async function parseError(res: Response): Promise<ApiError> {
  let code = "http_error";
  let message = `Request failed (${res.status})`;
  try {
    const body = await res.json();
    if (body?.error) {
      code = body.error.code ?? code;
      message = body.error.message ?? message;
    } else if (typeof body?.detail === "string") {
      message = body.detail;
    } else if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
      code = "validation_error";
      message = body.detail[0].msg;
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(res.status, code, message);
}

export async function refreshSession(): Promise<boolean> {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!refresh) return false;
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${API_URL}/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: refresh }),
        });
        if (!res.ok) return false;
        const data = await res.json();
        tokens.set(data.access_token, data.refresh_token);
        return true;
      } catch {
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

export async function apiFetch(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });

  if (res.status === 401 && retry && tokens.hasRefresh()) {
    if (await refreshSession()) return apiFetch(path, init, false);
    tokens.clear();
    onAuthLost?.();
  }
  return res;
}

/** JSON helper: throws ApiError on non-2xx. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await apiFetch(path, init);
  if (!res.ok) throw await parseError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
