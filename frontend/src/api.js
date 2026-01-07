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
  const url = path.startsWith("http") ? path : `${BASE_URL}${path}`;
  const opts = { credentials: "include", ...options };
  return fetch(url, opts);
}
