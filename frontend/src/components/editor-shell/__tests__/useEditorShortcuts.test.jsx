// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { useEditorShortcuts } from "../useEditorShortcuts";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

function Harness({ handlers }) {
  useEditorShortcuts(handlers);
  return (
    <>
      <input data-testid="plain" />
      <input data-testid="shortcut" data-shortcut-input="true" />
    </>
  );
}

function press(target, key, extra = {}) {
  target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, ...extra }));
}

describe("useEditorShortcuts", () => {
  let container;
  let root;
  let handlers;

  beforeEach(() => {
    handlers = { j: vi.fn(), 1: vi.fn() };
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => root.render(<Harness handlers={handlers} />));
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it("fires a shortcut pressed on the page", () => {
    press(document.body, "j");
    expect(handlers.j).toHaveBeenCalledTimes(1);
  });

  it("ignores keys pressed with Cmd, Ctrl or Alt", () => {
    press(document.body, "1", { metaKey: true });
    press(document.body, "1", { ctrlKey: true });
    press(document.body, "j", { altKey: true });
    expect(handlers[1]).not.toHaveBeenCalled();
    expect(handlers.j).not.toHaveBeenCalled();
  });

  it("ignores everything typed into an ordinary input", () => {
    press(container.querySelector('[data-testid="plain"]'), "j");
    press(container.querySelector('[data-testid="plain"]'), "1");
    expect(handlers.j).not.toHaveBeenCalled();
    expect(handlers[1]).not.toHaveBeenCalled();
  });

  it("lets only digit shortcuts through a shortcut-enabled input", () => {
    const input = container.querySelector('[data-testid="shortcut"]');
    press(input, "j");
    press(input, "1");
    expect(handlers.j).not.toHaveBeenCalled();
    expect(handlers[1]).toHaveBeenCalledTimes(1);
  });
});
