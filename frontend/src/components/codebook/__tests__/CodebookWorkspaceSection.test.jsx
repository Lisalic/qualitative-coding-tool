// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import CodebookWorkspaceSection from "../CodebookWorkspaceSection";
import { groupCodesByFamily } from "../../../lib/codingUtils";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const tree = groupCodesByFamily([
  {
    code_uid: "c1",
    family_uid: "f1",
    family_name: "Coping",
    name: "Avoidance",
    definition: "Steering clear of the stressor",
  },
]);

const baseProps = {
  selectedCodebook: "42",
  selectedCodebookName: "My Codebook",
  codebookTree: tree,
  loading: false,
  error: null,
  isEditMode: false,
  codebookDraft: [],
  setCodebookDraft: () => {},
  saveState: { status: "idle", message: "" },
  onBeginEdit: () => {},
  onCancelEdit: () => {},
  onSaveEdit: () => {},
};

describe("CodebookWorkspaceSection", () => {
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

  const render = (props) =>
    act(() => {
      root.render(
        <MemoryRouter>
          <CodebookWorkspaceSection {...baseProps} {...props} />
        </MemoryRouter>,
      );
    });

  it("renders the codebook's families instead of 'codebook not found'", () => {
    render();
    expect(container.textContent).not.toContain("codebook not found");
    expect(container.textContent).toContain("Coping");
  });

  it("renders the draft in edit mode and saves with the edited name", () => {
    const onSaveEdit = vi.fn();
    render({ isEditMode: true, codebookDraft: tree, onSaveEdit });
    expect(container.textContent).not.toContain("codebook not found");
    const inputValues = [...container.querySelectorAll("input")].map((i) => i.value);
    expect(inputValues).toContain("Coping");

    const save = [...container.querySelectorAll("button")].find((b) => b.textContent === "Save");
    act(() => {
      save.click();
    });
    expect(onSaveEdit).toHaveBeenCalledWith("My Codebook");
  });
});
