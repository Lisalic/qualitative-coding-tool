// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import ProjectDownloadModal from "../ProjectDownloadModal";
import * as api from "../../../api";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const project = {
  id: 7,
  projectname: "My Project",
  files: [
    { file_type: "codebook" },
    { file_type: "coding" },
    { file_type: "codebook_comparison" },
  ],
};

/** The checkbox labelled `text` inside the fieldset whose legend starts with `kind`. */
function checkboxByLabel(container, kind, text) {
  const fieldset = [...container.querySelectorAll("fieldset")].find((f) =>
    f.querySelector("legend").textContent.startsWith(kind),
  );
  const label = [...fieldset.querySelectorAll("label")].find((l) => l.textContent.trim() === text);
  return label?.querySelector("input");
}

function downloadButton(container) {
  return [...container.querySelectorAll("button")].find((b) => b.textContent === "Download");
}

describe("ProjectDownloadModal", () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
    vi.restoreAllMocks();
  });

  it("lists each kind the project holds, Word/Excel ticked by default", () => {
    act(() => {
      root.render(<ProjectDownloadModal project={project} onClose={() => {}} />);
    });

    const legends = [...container.querySelectorAll("legend")].map((l) => l.textContent);
    expect(legends).toEqual([
      "Codebooks (1)",
      "Codings (1)",
      "Comparisons (1)",
      "Row memos (where written) (1)",
    ]);
    expect(checkboxByLabel(container, "Codebooks", "Word document (.docx)").checked).toBe(true);
    expect(checkboxByLabel(container, "Codebooks", "REFI-QDA codebook (.qdc)").checked).toBe(false);
    expect(checkboxByLabel(container, "Codings", "Excel workbook (.xlsx)").checked).toBe(true);
    expect(checkboxByLabel(container, "Comparisons", "Word document (.docx)").checked).toBe(true);
  });

  it("blocks download when a kind has no format ticked", () => {
    act(() => {
      root.render(<ProjectDownloadModal project={project} onClose={() => {}} />);
    });

    act(() => {
      checkboxByLabel(container, "Codebooks", "Word document (.docx)").click();
    });
    expect(downloadButton(container).disabled).toBe(true);
    expect(container.textContent).toContain("Pick at least one format.");
  });

  it("requests every ticked format for a kind", async () => {
    const apiFetch = vi.spyOn(api, "apiFetch").mockResolvedValue({
      ok: true,
      headers: { get: () => null },
      blob: async () => new Blob(["zip"]),
    });
    window.URL.createObjectURL = vi.fn(() => "blob:x");
    window.URL.revokeObjectURL = vi.fn();
    const onClose = vi.fn();

    act(() => {
      root.render(<ProjectDownloadModal project={project} onClose={onClose} />);
    });
    act(() => {
      checkboxByLabel(container, "Codebooks", "REFI-QDA codebook (.qdc)").click();
      checkboxByLabel(container, "Codings", "JSON (.json)").click();
      checkboxByLabel(container, "Comparisons", "Markdown (.md)").click();
    });
    await act(async () => {
      downloadButton(container).click();
    });

    expect(apiFetch).toHaveBeenCalledWith(
      "/api/export/projects/7/bundle?codebook_formats=docx&codebook_formats=qdc" +
        "&coding_formats=xlsx&coding_formats=json&comparison_formats=docx&comparison_formats=md" +
        "&memo_formats=docx",
    );
    expect(onClose).toHaveBeenCalled();
  });
});
