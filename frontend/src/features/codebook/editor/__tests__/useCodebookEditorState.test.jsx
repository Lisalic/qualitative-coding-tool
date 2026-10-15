// @vitest-environment jsdom
import { afterEach, expect, it } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { useCodebookEditorState } from "../useCodebookEditorState";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let editor;
function Harness() {
  editor = useCodebookEditorState("");
  return null;
}

const container = document.createElement("div");
document.body.appendChild(container);
const root = createRoot(container);

afterEach(() => {
  act(() => editor.clearDraft());
});

it("keeps edits made after a save starts", () => {
  act(() => root.render(<Harness />));
  act(() => editor.updateDraft([{ family_name: "Sent", codes: [] }]));
  const submittedState = editor.snapshot();
  act(() => editor.updateDraft([{ family_name: "New edit", codes: [] }]));

  expect(editor.clearDraftIfUnchanged(submittedState)).toBe(false);
  expect(editor.draft[0].family_name).toBe("New edit");

  act(() => expect(editor.clearDraftIfUnchanged(editor.snapshot())).toBe(true));
  expect(editor.draft).toEqual([]);
});
