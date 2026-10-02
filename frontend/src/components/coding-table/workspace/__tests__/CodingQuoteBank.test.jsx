// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import CodingQuoteBank from "../CodingQuoteBank";
import * as api from "../../../../api";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

describe("CodingQuoteBank (QC-008)", () => {
  let container;
  let root;

  const mockQuotesData = {
    quotes: [
      {
        id: 101,
        quote: "Direct evidence of participant engagement.",
        code: "Engagement",
        coder: "human",
        post_id: "post_1",
        row_type: "submission",
        start_offset: 10,
        end_offset: 52,
        starred: false,
        notes: "Key finding",
        title: "Community Post 1",
        content: "We noticed direct evidence of participant engagement across threads.",
        subreddit: "qual",
        author: "alice",
      },
      {
        id: 102,
        quote: "Automated tagging was verified by human coder.",
        code: "Verification",
        coder: "ai",
        coder_model: "gpt-4o",
        post_id: "post_2",
        row_type: "submission",
        start_offset: 0,
        end_offset: 46,
        starred: true,
        notes: null,
        title: "Community Post 2",
        content: "Automated tagging was verified by human coder.",
        subreddit: "ai",
        author: "bob",
      },
    ],
    total: 2,
  };

  const availableCodes = [
    { name: "Engagement", code_uid: "c1" },
    { name: "Verification", code_uid: "c2" },
  ];

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);

    // Mock apiFetch for quote listing
    vi.spyOn(api, "apiFetch").mockImplementation((url) => {
      if (url.includes("/quotes?")) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => mockQuotesData,
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({}),
      });
    });

    // Star/note writes go through requestJson ({ ok, data, error }).
    vi.spyOn(api, "requestJson").mockImplementation((url, { body }) => {
      if (url.includes("/star")) {
        const entryId = Number(url.match(/quotes\/(\d+)\/star/)[1]);
        return Promise.resolve({ ok: true, status: 200, data: { entry_id: entryId, starred: body.starred } });
      }
      if (url.includes("/notes")) {
        // A note edit mints a new version -> the quote comes back re-keyed.
        return Promise.resolve({ ok: true, status: 200, data: { entry_id: 555, notes: body.notes } });
      }
      return Promise.resolve({ ok: true, status: 200, data: {} });
    });

    // Mock clipboard
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.restoreAllMocks();
  });

  it("renders quote rows with exact offsets, badges, and notes", async () => {
    await act(async () => {
      root.render(<CodingQuoteBank schema="proj_test" availableCodes={availableCodes} />);
    });

    expect(container.textContent).toContain("Direct evidence of participant engagement.");
    expect(container.textContent).toContain("Automated tagging was verified by human coder.");
    expect(container.textContent).toContain("Engagement");
    expect(container.textContent).toContain("Verification");
    expect(container.textContent).toContain("[10:52]");
    expect(container.textContent).toContain("[0:46]");
    expect(container.textContent).toContain("HUMAN");
    expect(container.textContent).toContain("AI: gpt-4o");
    expect(container.textContent).toContain("Key finding");
  });

  it("filters quotes by code, coder, and starred-only", async () => {
    await act(async () => {
      root.render(<CodingQuoteBank schema="proj_test" availableCodes={availableCodes} />);
    });

    const codeSelect = container.querySelector('select[aria-label="Filter by code"]');
    expect(codeSelect).not.toBeNull();

    // Filters by stable code_uid, not display name, so a rename can't break it.
    await act(async () => {
      codeSelect.value = "c1";
      codeSelect.dispatchEvent(new Event("change", { bubbles: true }));
    });

    expect(api.apiFetch).toHaveBeenCalledWith(
      expect.stringContaining("code=c1")
    );

    const coderSelect = container.querySelector('select[aria-label="Filter by coder"]');
    await act(async () => {
      coderSelect.value = "ai";
      coderSelect.dispatchEvent(new Event("change", { bubbles: true }));
    });

    expect(api.apiFetch).toHaveBeenCalledWith(
      expect.stringContaining("coder=ai")
    );

    const starredBtn = container.querySelector('button[title="Filter by starred quotes"]');
    await act(async () => {
      starredBtn.click();
    });

    expect(api.apiFetch).toHaveBeenCalledWith(
      expect.stringContaining("starred_only=true")
    );
  });

  it("toggles quote star with optimistic update and API call", async () => {
    await act(async () => {
      root.render(<CodingQuoteBank schema="proj_test" availableCodes={availableCodes} />);
    });

    const starBtn = container.querySelector('button[aria-label="Star quote"]');
    expect(starBtn).not.toBeNull();

    await act(async () => {
      starBtn.click();
    });

    expect(api.requestJson).toHaveBeenCalledWith(
      "/api/coding/proj_test/quotes/101/star",
      { method: "PUT", body: { starred: true } },
    );
    expect(container.querySelectorAll('button[aria-label="Unstar quote"]').length).toBe(2);
  });

  it("shows a visible error and reverts when starring fails", async () => {
    api.requestJson.mockImplementation(() =>
      Promise.resolve({ ok: false, status: 500, data: null, error: "Server exploded" }),
    );
    await act(async () => {
      root.render(<CodingQuoteBank schema="proj_test" availableCodes={availableCodes} />);
    });

    await act(async () => {
      container.querySelector('button[aria-label="Star quote"]').click();
    });

    expect(container.querySelector('[role="alert"]').textContent).toContain("Server exploded");
    expect(container.querySelector('button[aria-label="Star quote"]')).not.toBeNull();
  });

  it("keeps the Inspect dialog's star button in sync", async () => {
    await act(async () => {
      root.render(<CodingQuoteBank schema="proj_test" availableCodes={availableCodes} />);
    });

    const inspectBtn = Array.from(container.querySelectorAll("button")).find(
      (b) => b.textContent === "Inspect Source",
    );
    await act(async () => {
      inspectBtn.click();
    });
    const dialogStar = () =>
      Array.from(container.querySelectorAll('[role="dialog"] button')).find((b) =>
        b.textContent.includes("Star"),
      );
    expect(dialogStar().textContent).toBe("☆ Star");

    await act(async () => {
      dialogStar().click();
    });
    expect(dialogStar().textContent).toBe("★ Starred");

    await act(async () => {
      dialogStar().click();
    });
    expect(api.requestJson).toHaveBeenLastCalledWith(
      "/api/coding/proj_test/quotes/101/star",
      { method: "PUT", body: { starred: false } },
    );
  });

  it("attaches and edits quote notes", async () => {
    await act(async () => {
      root.render(<CodingQuoteBank schema="proj_test" availableCodes={availableCodes} />);
    });

    const editBtn = container.querySelector('button[title="Edit note (e)"]');
    expect(editBtn).not.toBeNull();

    await act(async () => {
      editBtn.click();
    });

    const textarea = container.querySelector("textarea");
    expect(textarea).not.toBeNull();
    expect(textarea.value).toBe("Key finding");

    await act(async () => {
      const nativeSetter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        "value"
      ).set;
      nativeSetter.call(textarea, "Updated note text");
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      textarea.dispatchEvent(new Event("change", { bubbles: true }));
    });

        const saveNoteBtn = Array.from(container.querySelectorAll("button")).find(
      (b) => b.textContent === "Save Note"
    );
    expect(saveNoteBtn).not.toBeNull();

    await act(async () => {
      saveNoteBtn.click();
    });

    expect(api.requestJson).toHaveBeenCalledWith(
      "/api/coding/proj_test/quotes/101/notes",
      { method: "PATCH", body: { notes: "Updated note text" } },
    );
    expect(container.textContent).toContain("Updated note text");

    // The quote was re-keyed to the new entry id, so starring targets it.
    await act(async () => {
      container.querySelector('button[aria-label="Star quote"]').click();
    });
    expect(api.requestJson).toHaveBeenLastCalledWith(
      "/api/coding/proj_test/quotes/555/star",
      { method: "PUT", body: { starred: true } },
    );
  });

  it("leaves Enter to a focused button instead of opening Inspect", async () => {
    await act(async () => {
      root.render(<CodingQuoteBank schema="proj_test" availableCodes={availableCodes} />);
    });

    const starBtn = container.querySelector('button[aria-label="Star quote"]');
    await act(async () => {
      starBtn.focus();
      starBtn.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
      starBtn.dispatchEvent(new KeyboardEvent("keydown", { key: "s", bubbles: true }));
    });

    expect(container.querySelector('[role="dialog"]')).toBeNull();
    expect(api.requestJson).not.toHaveBeenCalled();
  });

  it("supports keyboard navigation: j/k selection, s to star, Enter to inspect", async () => {
    await act(async () => {
      root.render(<CodingQuoteBank schema="proj_test" availableCodes={availableCodes} />);
    });

    const rows = container.querySelectorAll('[tabindex="0"]');
    expect(rows.length).toBe(2);

    // Initial focus on row 0
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "j" }));
    });

    // Press 's' to toggle star on row 1 (quote 102)
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "s" }));
    });

    expect(api.requestJson).toHaveBeenCalledWith(
      "/api/coding/proj_test/quotes/102/star",
      { method: "PUT", body: { starred: false } },
    );

    // Press 'Enter' or 'o' to inspect source context
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter" }));
    });

    const inspectDialog = container.querySelector('[role="dialog"]');
    expect(inspectDialog).not.toBeNull();
    expect(inspectDialog.textContent).toContain("Source Context Inspection");
    expect(inspectDialog.textContent).toContain("Offsets: [0:46]");

    // Close inspect with Escape
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    });

    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });

  it("opens citation modal and copies formatted citation without author/url by default", async () => {
    await act(async () => {
      root.render(<CodingQuoteBank schema="proj_test" availableCodes={availableCodes} />);
    });

    const citationBtn = container.querySelector('button[title*="Copy citation"]');
    expect(citationBtn).not.toBeNull();

    await act(async () => {
      citationBtn.click();
    });

    const dialog = container.querySelector('[role="dialog"]');
    expect(dialog).not.toBeNull();
    expect(dialog.textContent).toContain("Copy Citation for Writing Draft");
    expect(dialog.textContent).toContain("Attribution Fields (Privacy Guardrails)");

    // Default citation preview check
    const preview = dialog.querySelector("pre");
    expect(preview.textContent).toContain('"Direct evidence of participant engagement."');
    expect(preview.textContent).toContain("Code: Engagement");
    expect(preview.textContent).toContain("Coder: Human");
    // Privacy defaults: author and url NOT in preview
    expect(preview.textContent).not.toContain("alice");
    expect(preview.textContent).not.toContain("http");

    const copyBtn = Array.from(dialog.querySelectorAll("button")).find(
      (b) => b.textContent === "Copy to Clipboard"
    );
    expect(copyBtn).not.toBeNull();

    await act(async () => {
      copyBtn.click();
    });

    expect(navigator.clipboard.writeText).toHaveBeenCalled();
    expect(container.textContent).toContain("Citation copied to clipboard");
  });
});
