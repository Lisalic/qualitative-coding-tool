// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { BASE_URL, apiFetch, postForm } from "../api";

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

  it("network throw with a message -> status 0, error is the message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("boom")));
    const result = await postForm("/api/x", new FormData());
    expect(result).toEqual({ ok: false, status: 0, data: null, error: "boom" });
  });

  it("network throw with no message (e.g. a thrown string) -> generic 'Network error'", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => Promise.reject("boom-string")),
    );
    const result = await postForm("/api/x", new FormData());
    expect(result).toEqual({ ok: false, status: 0, data: null, error: "Network error" });
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

  it("array detail: empty array falls back to the generic HTTP error string", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 500, body: { detail: [] } })),
    );
    const result = await postForm("/api/x", new FormData());
    expect(result.error).toBe("HTTP error 500");
  });

  it("error without a JSON body but with raw text -> error is the raw text verbatim", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 500, body: "plain text error" })),
    );
    const result = await postForm("/api/x", new FormData());
    expect(result.error).toBe("plain text error");
  });

  it("error with an empty body -> generic 'HTTP error <status>'", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 500, body: "" })));
    const result = await postForm("/api/x", new FormData());
    expect(result.error).toBe("HTTP error 500");
  });

  it("preserves the parsed data on a failure response", async () => {
    const body = { error: "E", extra: "field" };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(mockResponse({ ok: false, status: 400, body })));
    const result = await postForm("/api/x", new FormData());
    expect(result.data).toEqual(body);
  });
});
