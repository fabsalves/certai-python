import axios from "axios";

const ACCESS = "certai.access";
const REFRESH = "certai.refresh";

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS);
  },
  get refresh() {
    return localStorage.getItem(REFRESH);
  },
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS, access);
    localStorage.setItem(REFRESH, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
  },
};

export const api = axios.create({ baseURL: "/api/v1" });

export function apiErrorMessage(err: unknown, fallback: string): string {
  if (!axios.isAxiosError(err)) return fallback;
  const detail = err.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (typeof first === "string") return first;
    if (first && typeof first === "object" && "msg" in first && typeof first.msg === "string") {
      return first.msg.replace(/^Value error,\s*/i, "");
    }
  }
  return fallback;
}

api.interceptors.request.use((config) => {
  const t = tokens.access;
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

// Renova o access token uma vez ao receber 401, depois repete a requisição.
let refreshing: Promise<string> | null = null;

api.interceptors.response.use(
  (r) => r,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && !original._retry && tokens.refresh) {
      original._retry = true;
      try {
        refreshing ??= axios
          .post("/api/v1/auth/refresh", { refresh_token: tokens.refresh })
          .then((res) => {
            tokens.set(res.data.access_token, res.data.refresh_token);
            return res.data.access_token as string;
          })
          .finally(() => {
            refreshing = null;
          });
        const newAccess = await refreshing;
        original.headers.Authorization = `Bearer ${newAccess}`;
        return api(original);
      } catch {
        tokens.clear();
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);
