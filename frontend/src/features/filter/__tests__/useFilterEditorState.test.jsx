// @vitest-environment jsdom
import { expect, it } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { useFilterEditorState } from "../useFilterEditorState";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

it("keeps a decision made while the submitted filter is saving", () => {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  let editor;
  function Harness() {
    editor = useFilterEditorState("");
    return null;
  }

  act(() => root.render(<Harness />));
  act(() => editor.include("submission", "sent"));
  const submittedSelection = editor.snapshot();
  act(() => editor.include("submission", "new"));

  expect(editor.clearDraftIfUnchanged(submittedSelection)).toBe(false);
  expect(editor.included.postIds).toContain("new");

  act(() => root.unmount());
  container.remove();
});
