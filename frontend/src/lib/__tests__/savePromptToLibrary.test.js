import { describe, it, expect, vi, beforeEach } from "vitest";
import { savePromptToLibrary } from "../savePromptToLibrary";
import { api } from "../../api";

vi.mock("../../api", () => ({
  api: { get: vi.fn(), post: vi.fn() },
}));

beforeEach(() => {
  vi.clearAllMocks();
});

describe("savePromptToLibrary", () => {
  it("throws EMPTY_PROMPT for blank/whitespace-only text, without calling the API", async () => {
    await expect(savePromptToLibrary("filter", "   ")).rejects.toThrow("EMPTY_PROMPT");
    expect(api.get).not.toHaveBeenCalled();
    expect(api.post).not.toHaveBeenCalled();
  });

  it("throws EMPTY_PROMPT for an empty string", async () => {
    await expect(savePromptToLibrary("filter", "")).rejects.toThrow("EMPTY_PROMPT");
  });

  it("swallows a failing /api/me/ call and proceeds without user_id", async () => {
    api.get.mockImplementation((url) => {
      if (url === "/api/me/") return Promise.reject(new Error("unauthorized"));
      return Promise.resolve({ data: { prompts: [] } });
    });
    api.post.mockResolvedValue({ data: { promptname: "Prompt 1" } });

    const result = await savePromptToLibrary("filter", "some prompt text");
    expect(result).toEqual({ label: "Prompt 1" });

    const postedForm = api.post.mock.calls[0][1];
    expect(postedForm.has("user_id")).toBe(false);
  });

  it("includes user_id when /api/me/ succeeds", async () => {
    api.get.mockImplementation((url) => {
      if (url === "/api/me/") return Promise.resolve({ data: { id: "42" } });
      return Promise.resolve({ data: { prompts: [] } });
    });
    api.post.mockResolvedValue({ data: { promptname: "Prompt 1" } });

    await savePromptToLibrary("filter", "text");
    const postedForm = api.post.mock.calls[0][1];
    expect(postedForm.get("user_id")).toBe("42");
  });

  it("falls back to sub when id is absent on /api/me/", async () => {
    api.get.mockImplementation((url) => {
      if (url === "/api/me/") return Promise.resolve({ data: { sub: "7" } });
      return Promise.resolve({ data: { prompts: [] } });
    });
    api.post.mockResolvedValue({ data: {} });

    await savePromptToLibrary("filter", "text");
    const postedForm = api.post.mock.calls[0][1];
    expect(postedForm.get("user_id")).toBe("7");
  });

  it("names the prompt by count+1 when the prompt list succeeds", async () => {
    api.get.mockImplementation((url) => {
      if (url === "/api/me/") return Promise.reject(new Error("x"));
      return Promise.resolve({ data: { prompts: [{}, {}] } });
    });
    api.post.mockResolvedValue({ data: {} });

    await savePromptToLibrary("generate", "text");
    const postedForm = api.post.mock.calls[0][1];
    expect(postedForm.get("promptname")).toBe("Prompt 3");
  });

  it("falls back to a Date.now()-based name when the prompt list call fails", async () => {
    vi.spyOn(Date, "now").mockReturnValue(1234567890);
    api.get.mockImplementation((url) => {
      if (url === "/api/me/") return Promise.reject(new Error("x"));
      return Promise.reject(new Error("list failed"));
    });
    api.post.mockResolvedValue({ data: {} });

    await savePromptToLibrary("apply", "text");
    const postedForm = api.post.mock.calls[0][1];
    expect(postedForm.get("promptname")).toBe("Prompt 1234567890");
    Date.now.mockRestore();
  });

  it("posts the trimmed prompt text and type", async () => {
    api.get.mockRejectedValue(new Error("x"));
    api.post.mockResolvedValue({ data: {} });

    await savePromptToLibrary("filter", "  padded text  ");
    const postedForm = api.post.mock.calls[0][1];
    expect(postedForm.get("prompt")).toBe("padded text");
    expect(postedForm.get("type")).toBe("filter");
  });

  it("label resolution: promptname wins over display_name and prompt", async () => {
    api.get.mockRejectedValue(new Error("x"));
    api.post.mockResolvedValue({
      data: { promptname: "A", display_name: "B", prompt: "C" },
    });
    const result = await savePromptToLibrary("filter", "text");
    expect(result.label).toBe("A");
  });

  it("label resolution: falls back to display_name, then prompt, then default", async () => {
    api.get.mockRejectedValue(new Error("x"));

    api.post.mockResolvedValueOnce({ data: { display_name: "B", prompt: "C" } });
    expect((await savePromptToLibrary("filter", "text")).label).toBe("B");

    api.post.mockResolvedValueOnce({ data: { prompt: "C" } });
    expect((await savePromptToLibrary("filter", "text")).label).toBe("C");

    api.post.mockResolvedValueOnce({ data: {} });
    expect((await savePromptToLibrary("filter", "text")).label).toBe("Prompt saved");
  });
});
