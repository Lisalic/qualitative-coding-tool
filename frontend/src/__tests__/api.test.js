// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  BASE_URL,
  NETWORK_ERROR_MESSAGE,
  apiFetch,
  postForm,
  postFormAndPoll,
  requestJson,
  postJsonAndPoll,
} from "../api";

function mockResponse({ ok, status, body }) {
  const rawText = typeof body === "string" ? body : body === undefined ? "" : JSON.stringify(body);
  return { ok, status, text: async () => rawText };
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("apiFetch", () => {
  it("ends the session when a request carrying a token gets a 401", async () => {
    localStorage.setItem("access_token", "expired");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 401 })));
    const onAuthChanged = vi.fn();
    window.addEventListener("auth-changed", onAuthChanged);

    await apiFetch("/api/projects/");

    window.removeEventListener("auth-changed", onAuthChanged);
    expect(localStorage.getItem("access_token")).toBeNull();
    expect(onAuthChanged).toHaveBeenCalledTimes(1);
  });

  it("leaves auth alone on a 401 for a request without a token", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 401 })));
    const onAuthChanged = vi.fn();
    window.addEventListener("auth-changed", onAuthChanged);

    await apiFetch("/api/me/");

    window.removeEventListener("auth-changed", onAuthChanged);
    expect(onAuthChanged).not.toHaveBeenCalled();
  });

  it("passes an absolute URL straight through to fetch, unjoined", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("http://other-host.example/x");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://other-host.example/x",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("does NOT attach an Authorization header on the absolute-URL branch, even with a token set", async () => {
    localStorage.setItem("access_token", "tok123");
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("http://other-host.example/x");
    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.headers).toBeUndefined();
  });

  it("joins a relative path onto BASE_URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/x");
    expect(fetchMock).toHaveBeenCalledWith(`${BASE_URL}/api/x`, expect.anything());
  });

  it("joins a relative path with no leading slash the same way", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("api/x");
    expect(fetchMock).toHaveBeenCalledWith(`${BASE_URL}/api/x`, expect.anything());
  });

  it("collapses multiple leading slashes in the path", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("///api/x");
    expect(fetchMock).toHaveBeenCalledWith(`${BASE_URL}/api/x`, expect.anything());
  });

  it("preserves an interior double slash in the path", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api//x");
    expect(fetchMock).toHaveBeenCalledWith(`${BASE_URL}/api//x`, expect.anything());
  });

  it("caller-supplied options (e.g. credentials) override the default", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/x", { credentials: "omit", method: "DELETE" });
    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.credentials).toBe("omit");
    expect(opts.method).toBe("DELETE");
  });

  it("attaches Authorization: Bearer <token> when a token is present", async () => {
    localStorage.setItem("access_token", "tok123");
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/x");
    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.headers.Authorization).toBe("Bearer tok123");
  });

  it("attaches no Authorization header when there is no token", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/x");
    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.headers.Authorization).toBeUndefined();
  });

  it("empty-string token is falsy -- no Authorization header (boundary)", async () => {
    localStorage.setItem("access_token", "");
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/x");
    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.headers.Authorization).toBeUndefined();
  });

  it("preserves caller-supplied plain-object headers alongside Authorization", async () => {
    localStorage.setItem("access_token", "tok123");
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/x", { headers: { "X-Custom": "yes" } });
    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.headers["X-Custom"]).toBe("yes");
    expect(opts.headers.Authorization).toBe("Bearer tok123");
  });

  it("the stored-token Authorization overwrites a caller-supplied Authorization header", async () => {
    localStorage.setItem("access_token", "server-token");
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/x", { headers: { Authorization: "Bearer caller-token" } });
    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.headers.Authorization).toBe("Bearer server-token");
  });
});

describe("postForm", () => {
  it("delegates to apiFetch with method POST and the given body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { a: 1 } }));
    vi.stubGlobal("fetch", fetchMock);
    const fd = new FormData();

    const result = await postForm("/api/x", fd);
    expect(result).toEqual({ ok: true, status: 200, data: { a: 1 }, error: null });
    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.method).toBe("POST");
    expect(opts.body).toBe(fd);
    expect(opts.credentials).toBe("include");
  });

  it("network throw -> status 0 with a plain-language connection message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("Failed to fetch")));
    const result = await postForm("/api/x", new FormData());
    expect(result).toEqual({ ok: false, status: 0, data: null, error: NETWORK_ERROR_MESSAGE });
  });

  it("network throw with no message (e.g. a thrown string) -> the same connection message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => Promise.reject("boom-string")),
    );
    const result = await postForm("/api/x", new FormData());
    expect(result).toEqual({ ok: false, status: 0, data: null, error: NETWORK_ERROR_MESSAGE });
  });

  it("success with an empty body -> data: null, ok: true", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 204, body: "" })));
    const result = await postForm("/api/x", new FormData());
    expect(result).toEqual({ ok: true, status: 204, data: null, error: null });
  });

  it("success with a non-JSON body -> data: null, still ok: true (silent data loss)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: "<html>not json</html>" })),
    );
    const result = await postForm("/api/x", new FormData());
    expect(result).toEqual({ ok: true, status: 200, data: null, error: null });
  });

  it("error with a string `error` field takes precedence over `detail`", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        mockResponse({ ok: false, status: 400, body: { error: "E", detail: "D" } }),
      ),
    );
    const result = await postForm("/api/x", new FormData());
    expect(result.error).toBe("E");
  });

  it("error with a string `detail` field is used when `error` is absent", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 400, body: { detail: "D" } })),
    );
    const result = await postForm("/api/x", new FormData());
    expect(result.error).toBe("D");
  });

  it("FastAPI 422 array detail: uses only the LAST loc segment, not a dotted path", async () => {
    const body = { detail: [{ loc: ["body", "api_key"], msg: "field required" }] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 422, body })));
    const result = await postForm("/api/x", new FormData());
    expect(result.error).toBe("api_key: field required");
  });

  it("array detail: multiple entries are joined with '; '", async () => {
    const body = {
      detail: [
        { loc: ["body", "a"], msg: "required" },
        { loc: ["body", "b"], msg: "required" },
      ],
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 422, body })));
    const result = await postForm("/api/x", new FormData());
    expect(result.error).toBe("a: required; b: required");
  });

  it("array detail: missing/non-array loc falls back to bare msg", async () => {
    const body = { detail: [{ msg: "just a message" }] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 422, body })));
    const result = await postForm("/api/x", new FormData());
    expect(result.error).toBe("just a message");
  });

  it("array detail: empty array falls back to the generic server-error string", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 500, body: { detail: [] } })),
    );
    const result = await postForm("/api/x", new FormData());
    expect(result.error).toBe("Server error (HTTP 500). Please try again.");
  });

  it("error without a JSON body but with raw text -> error is the raw text verbatim", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 500, body: "plain text error" })),
    );
    const result = await postForm("/api/x", new FormData());
    expect(result.error).toBe("plain text error");
  });

  it("error with an empty body -> generic server-error string", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 500, body: "" })));
    const result = await postForm("/api/x", new FormData());
    expect(result.error).toBe("Server error (HTTP 500). Please try again.");
  });

  it("preserves the parsed data on a failure response", async () => {
    const body = { error: "E", extra: "field" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 400, body })));
    const result = await postForm("/api/x", new FormData());
    expect(result.data).toEqual(body);
  });
});

describe("requestJson", () => {
  it("sends a JSON body with a Content-Type header, defaulting to POST", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: { a: 1 } }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await requestJson("/api/coding/proj_1/rows", { body: { rows: [{ item_id: "t3_1" }] } });

    expect(result).toEqual({ ok: true, status: 200, data: { a: 1 }, error: null });
    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.method).toBe("POST");
    expect(opts.headers["Content-Type"]).toBe("application/json");
    expect(opts.body).toBe(JSON.stringify({ rows: [{ item_id: "t3_1" }] }));
  });

  it("honors a caller-supplied method (e.g. PUT/PATCH)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: true, status: 200, body: {} }));
    vi.stubGlobal("fetch", fetchMock);

    await requestJson("/api/coding/proj_1/codebook", { method: "PUT", body: { content: "x" } });

    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.method).toBe("PUT");
  });

  it("network throw -> status 0 with the plain-language connection message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("boom")));
    const result = await requestJson("/api/x", { body: {} });
    expect(result).toEqual({ ok: false, status: 0, data: null, error: NETWORK_ERROR_MESSAGE });
  });

  it("error response flattens FastAPI 422 detail the same way postForm does", async () => {
    const body = { detail: [{ loc: ["body", "item_ids"], msg: "field required" }] };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 422, body })));
    const result = await requestJson("/api/x", { body: {} });
    expect(result.error).toBe("item_ids: field required");
  });
});

describe("postJsonAndPoll", () => {
  it("kicks off with a JSON body and polls through to success", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mockResponse({ ok: true, status: 202, body: { job_id: 9, status: "pending" } }))
      .mockResolvedValueOnce(
        mockResponse({ ok: true, status: 200, body: { status: "succeeded", result: { recoded_item_count: 3 } } }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const result = await postJsonAndPoll(
      "/api/coding/proj_1/recode",
      { item_ids: ["t3_1"], api_key: "k" },
      { intervalMs: 1 },
    );

    expect(result).toEqual({ ok: true, status: 200, data: { recoded_item_count: 3 }, jobId: 9, error: null });
    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(opts.body)).toEqual({ item_ids: ["t3_1"], api_key: "k" });
  });

  it("a failing kickoff is returned as-is and never polls", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 400, body: { error: "bad" } }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await postJsonAndPoll("/api/x", {}, { intervalMs: 1 });

    expect(result).toEqual({ ok: false, status: 400, data: { error: "bad" }, error: "bad" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("postFormAndPoll", () => {
  it("kicks off, polls through a pending status, and resolves on success", async () => {
    const onStatusChange = vi.fn();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mockResponse({ ok: true, status: 202, body: { job_id: 42, status: "pending" } }))
      .mockResolvedValueOnce(mockResponse({ ok: true, status: 200, body: { status: "running" } }))
      .mockResolvedValueOnce(
        mockResponse({ ok: true, status: 200, body: { status: "succeeded", result: { summary: "done" } } }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const result = await postFormAndPoll("/api/x", new FormData(), { intervalMs: 1, onStatusChange });

    expect(result).toEqual({ ok: true, status: 200, data: { summary: "done" }, jobId: 42, error: null });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][0]).toBe(`${BASE_URL}/api/jobs/42`);
    expect(onStatusChange.mock.calls.map((c) => c[0])).toEqual(["running", "succeeded"]);
  });

  it("reports progress on every poll via onProgress", async () => {
    const onProgress = vi.fn();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mockResponse({ ok: true, status: 202, body: { job_id: 42, status: "pending" } }))
      .mockResolvedValueOnce(
        mockResponse({ ok: true, status: 200, body: { status: "running", progress: { current: 2, total: 5, label: "batches" } } }),
      )
      .mockResolvedValueOnce(
        mockResponse({ ok: true, status: 200, body: { status: "succeeded", result: {} } }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await postFormAndPoll("/api/x", new FormData(), { intervalMs: 1, onProgress });

    expect(onProgress.mock.calls).toEqual([
      [{ current: 2, total: 5, label: "batches" }],
      [null],
    ]);
  });

  it("resolves an error result when the job reaches a failed status", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mockResponse({ ok: true, status: 202, body: { job_id: 7, status: "pending" } }))
      .mockResolvedValueOnce(
        mockResponse({ ok: true, status: 200, body: { status: "failed", error: "boom" } }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const result = await postFormAndPoll("/api/x", new FormData(), { intervalMs: 1 });

    expect(result).toEqual({ ok: false, status: 200, data: null, error: "boom" });
  });

  it("a failing kickoff (e.g. 400) is returned as-is and never polls", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 400, body: { error: "bad schema" } }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await postFormAndPoll("/api/x", new FormData(), { intervalMs: 1 });

    expect(result).toEqual({ ok: false, status: 400, data: { error: "bad schema" }, error: "bad schema" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("times out if the job never reaches a terminal status within timeoutMs", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mockResponse({ ok: true, status: 202, body: { job_id: 1, status: "pending" } }))
      .mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: "pending" } }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await postFormAndPoll("/api/x", new FormData(), { intervalMs: 5, timeoutMs: 20 });

    expect(result.ok).toBe(false);
    expect(result.error).toMatch(/still running in the background/i);
  });

  it("stops early and resolves an aborted result when the AbortSignal fires mid-poll", async () => {
    const controller = new AbortController();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mockResponse({ ok: true, status: 202, body: { job_id: 1, status: "pending" } }))
      .mockResolvedValue(mockResponse({ ok: true, status: 200, body: { status: "pending" } }));
    vi.stubGlobal("fetch", fetchMock);

    const promise = postFormAndPoll("/api/x", new FormData(), {
      intervalMs: 5000,
      timeoutMs: 60000,
      signal: controller.signal,
    });
    // Let the kickoff + first poll resolve, then abort while it's sleeping
    // between polls (well before the 5s interval would otherwise elapse).
    setTimeout(() => controller.abort(), 5);

    const result = await promise;
    expect(result).toEqual({ ok: false, status: 0, data: null, error: "Aborted" });
  });

  it("returns a network-error result once polling keeps failing", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mockResponse({ ok: true, status: 202, body: { job_id: 1, status: "pending" } }))
      .mockRejectedValue(new Error("network down"));
    vi.stubGlobal("fetch", fetchMock);

    const result = await postFormAndPoll("/api/x", new FormData(), { intervalMs: 1 });

    expect(result).toMatchObject({ ok: false, status: 0, data: null });
    expect(result.error).toMatch(/may still be running/);
    // The kickoff plus five failed polls: one blip is not the end of the job.
    expect(fetchMock).toHaveBeenCalledTimes(6);
  });

  it("keeps waiting through a dropped poll or a brief 5xx", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mockResponse({ ok: true, status: 202, body: { job_id: 1, status: "pending" } }))
      .mockRejectedValueOnce(new Error("network down"))
      .mockResolvedValueOnce(mockResponse({ ok: false, status: 503, body: { error: "busy" } }))
      .mockResolvedValueOnce(mockResponse({ ok: true, status: 200, body: { status: "succeeded", result: { n: 1 } } }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await postFormAndPoll("/api/x", new FormData(), { intervalMs: 1 });

    expect(result.ok).toBe(true);
    expect(result.data).toEqual({ n: 1 });
  });

  it("stops at once on a non-transient error such as 404", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mockResponse({ ok: true, status: 202, body: { job_id: 1, status: "pending" } }))
      .mockResolvedValue(mockResponse({ ok: false, status: 404, body: { error: "Job not found" } }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await postFormAndPoll("/api/x", new FormData(), { intervalMs: 1 });

    expect(result).toEqual({ ok: false, status: 404, data: null, error: "Job not found" });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
