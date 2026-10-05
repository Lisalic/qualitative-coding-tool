// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import DialogHost from "../DialogHost";
import DialogService from "../DialogService";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

function buttonByText(container, text) {
  return Array.from(container.querySelectorAll("button")).find((b) => b.textContent.trim() === text);
}

describe("DialogHost", () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => root.render(<DialogHost />));
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("renders nothing when no dialog is queued", () => {
    expect(container.querySelector('[role="alertdialog"]')).toBeNull();
  });

  it("confirm resolves true when the confirm button is clicked", async () => {
    let promise;
    act(() => {
      promise = DialogService.confirm("Delete it?", { confirmLabel: "Delete", danger: true });
    });
    expect(container.textContent).toContain("Delete it?");
    act(() => buttonByText(container, "Delete").click());
    await expect(promise).resolves.toBe(true);
    expect(container.querySelector('[role="alertdialog"]')).toBeNull();
  });

  it("opens a destructive confirm on Cancel so Enter can't confirm it", () => {
    act(() => {
      DialogService.confirm("Delete it?", { confirmLabel: "Delete", danger: true });
    });
    expect(document.activeElement?.textContent).toBe("Cancel");
    act(() => DialogService.resolveCurrent(false));
  });

  it("confirm resolves false on Cancel and on Escape", async () => {
    let first;
    act(() => {
      first = DialogService.confirm("First?");
    });
    act(() => buttonByText(container, "Cancel").click());
    await expect(first).resolves.toBe(false);

    let second;
    act(() => {
      second = DialogService.confirm("Second?");
    });
    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })));
    await expect(second).resolves.toBe(false);
  });
});
