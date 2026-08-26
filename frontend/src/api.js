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

// Ensure axios instance uses Authorization header if token exists
try {
  if (typeof window !== "undefined") {
    const t = localStorage.getItem("access_token");
    if (t) api.defaults.headers.common["Authorization"] = `Bearer ${t}`;
  }
} catch (e) {}

// Normalizes a fetch Response into `{ ok, status, data, error }`, shared by
// `postForm` and `requestJson`. `error` is a human-readable string when
// `ok` is false: FastAPI 422 responses flatten the validation `detail`
// array; a 4xx/5xx with `{error: "..."}` returns that field directly.
async function _normalizeJsonResponse(response) {
  const rawText = await response.text();
  let parsed = null;
  try {
    parsed = rawText ? JSON.parse(rawText) : null;
  } catch {
    parsed = null;
  }

  if (response.ok) {
    return { ok: true, status: response.status, data: parsed, error: null };
  }

  let error = `HTTP error ${response.status}`;
  if (parsed) {
    if (typeof parsed.error === "string") {
      error = parsed.error;
    } else if (typeof parsed.detail === "string") {
      error = parsed.detail;
    } else if (Array.isArray(parsed.detail)) {
      error = parsed.detail
        .map((d) => {
          const loc = Array.isArray(d.loc) ? d.loc.slice(-1).join(".") : "";
          return loc ? `${loc}: ${d.msg}` : d.msg;
        })
        .filter(Boolean)
        .join("; ") || error;
    }
  } else if (rawText) {
    error = rawText;
  }

  return { ok: false, status: response.status, data: parsed, error };
}

/**
 * Post `FormData` to `path` and normalize the response into
 * `{ ok, status, data, error }`. See `_normalizeJsonResponse` for the
 * error-flattening rules.
 */
export async function postForm(path, formData) {
  let response;
  try {
    response = await apiFetch(path, { method: "POST", body: formData });
  } catch (err) {
    return {
      ok: false,
      status: 0,
      data: null,
      error: err?.message || "Network error",
    };
  }
  return _normalizeJsonResponse(response);
}

/**
 * Send a JSON body to `path` (default `POST`) and normalize the response
 * into `{ ok, status, data, error }` -- the JSON-body counterpart of
 * `postForm`, for the coding-artifact routes
 * (``PUT``/``PATCH``/``POST /api/coding/...``) that take a structured
 * body (e.g. a list of row edits) rather than flat form fields.
 */
export async function requestJson(path, { method = "POST", body } = {}) {
  let response;
  try {
    response = await apiFetch(path, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (err) {
    return {
      ok: false,
      status: 0,
      data: null,
      error: err?.message || "Network error",
    };
  }
  return _normalizeJsonResponse(response);
}

// Resolves `ms` milliseconds later, or immediately if `signal` is already
// aborted or gets aborted while waiting. Never rejects.
function _sleepOrAbort(ms, signal) {
  return new Promise((resolve) => {
    if (signal?.aborted) {
      resolve();
      return;
    }
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    function onAbort() {
      clearTimeout(timer);
      resolve();
    }
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

/**
 * POST `formData` to `path` (expects a `{job_id, status}` 202 response),
 * then poll `GET /api/jobs/{job_id}` until a terminal status, timeout, or
 * abort. Resolves to the same `{ok, status, data, error}` shape `postForm`
 * returns -- `data` is the job's `result` on success.
 *
 * This is the shared kickoff+poll helper for every AI-backed endpoint
 * converted to the background-job pattern (see backend/app/jobs/) --
 * `summarize-coding` first, more to follow -- so its shape is meant to
 * stay stable across all of them.
 *
 * `onProgress`, if given, is called on every poll with the job's
 * `progress` field (`{current, total, label}` or `null` if the handler
 * hasn't reported any yet) -- callers can feed this straight into a
 * progress-bar component.
 */
async function _pollJob(jobId, {
  intervalMs = 2000, timeoutMs = 600000, onStatusChange, onProgress, signal,
} = {}) {
  const deadline = Date.now() + timeoutMs;

  for (;;) {
    if (signal?.aborted) {
      return { ok: false, status: 0, data: null, error: "Aborted" };
    }

    let response;
    try {
      response = await apiFetch(`/api/jobs/${jobId}`);
    } catch (err) {
      return {
        ok: false,
        status: 0,
        data: null,
        error: err?.message || "Network error",
      };
    }

    const rawText = await response.text();
    let job = null;
    try {
      job = rawText ? JSON.parse(rawText) : null;
    } catch {
      job = null;
    }

    if (!response.ok) {
      const error = (job && typeof job.error === "string" && job.error) || `HTTP error ${response.status}`;
      return { ok: false, status: response.status, data: null, error };
    }

    const status = job?.status;
    onStatusChange?.(status);
    onProgress?.(job?.progress || null);

    if (status === "succeeded") {
      return { ok: true, status: 200, data: job.result, error: null };
    }
    if (status === "failed") {
      return { ok: false, status: 200, data: null, error: job.error || "Job failed" };
    }

    if (Date.now() >= deadline) {
      return {
        ok: false,
        status: 0,
        data: null,
        error: `Timed out waiting for job ${jobId} to complete`,
      };
    }

    await _sleepOrAbort(intervalMs, signal);

    if (signal?.aborted) {
      return { ok: false, status: 0, data: null, error: "Aborted" };
    }
  }
}

export async function postFormAndPoll(path, formData, opts = {}) {
  const kickoff = await postForm(path, formData);
  if (!kickoff.ok) {
    // Kickoff itself failed (e.g. a 400 validation error) -- nothing to poll.
    return kickoff;
  }
  return _pollJob(kickoff.data && kickoff.data.job_id, opts);
}

/**
 * JSON-body counterpart of `postFormAndPoll`, for job-kickoff routes that
 * take a structured JSON body (e.g. ``POST /api/coding/{ref}/recode``'s
 * list of selected row ids) rather than flat form fields. Same
 * `{ok, status, data, error}` result shape and polling options.
 */
export async function postJsonAndPoll(path, body, opts = {}) {
  const kickoff = await requestJson(path, { method: "POST", body });
  if (!kickoff.ok) {
    return kickoff;
  }
  return _pollJob(kickoff.data && kickoff.data.job_id, opts);
}
