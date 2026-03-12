import axios from "axios";

// Base URL used for all API requests. Prefers env var, falls back to localhost for dev.
export const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Axios instance with baseURL and credentials included for cookie auth.
export const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
});

// Fetch wrapper that prefixes the BASE_URL and includes credentials by default.
export async function apiFetch(path, options = {}) {
  if (path.startsWith("http")) {
    const opts = { credentials: "include", ...options };
    return fetch(path, opts);
  }

  // Ensure we join base and path without producing a double-slash
  const base = String(BASE_URL).replace(/\/+$/g, "");
  const rel = String(path).replace(/^\/+/g, "");
  const url = `${base}/${rel}`;
  const opts = { credentials: "include", ...options };
  // Attach Authorization header from localStorage token when present
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const headers = Object.assign({}, opts.headers || {});
  if (token) headers["Authorization"] = `Bearer ${token}`;
  opts.headers = headers;
  return fetch(url, opts);
}

// Convenience helpers for common patterns
export async function getJSON(path) {
  const resp = await apiFetch(path, {
    method: "GET",
    headers: { Accept: "application/json" },
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(
      `GET ${path} failed: ${resp.status} ${resp.statusText} ${text || ""}`,
    );
  }
  return resp.json();
}

export async function postJSON(path, body) {
  const resp = await apiFetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(body ?? {}),
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(
      `POST ${path} failed: ${resp.status} ${resp.statusText} ${text || ""}`,
    );
  }
  return resp.json();
}

export async function downloadFile(path) {
  const resp = await apiFetch(path, { method: "GET" });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(
      `Download ${path} failed: ${resp.status} ${resp.statusText} ${text || ""}`,
    );
  }
  return resp.blob();
}

// Ensure axios instance uses Authorization header if token exists
try {
  if (typeof window !== "undefined") {
    const t = localStorage.getItem("access_token");
    if (t) api.defaults.headers.common["Authorization"] = `Bearer ${t}`;
  }
} catch (e) {}
