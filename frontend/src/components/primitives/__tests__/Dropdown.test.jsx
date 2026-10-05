// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import Dropdown from "../Dropdown";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

describe("Dropdown empty states", () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  const open = () => act(() => container.querySelector("button").click());

  it("says there is nothing to pick when the list itself is empty", () => {
    act(() =>
      root.render(
        <Dropdown
          options={[]}
          onChange={() => {}}
          emptyMessage="No codebooks match that search."
          noOptionsMessage="No codebooks yet."
        />,
      ),
    );
    open();
    expect(document.body.textContent).toContain("No codebooks yet.");
    expect(document.body.textContent).not.toContain("match that search");
  });

  it("puts the active option on the focused trigger, not the list", () => {
    act(() =>
      root.render(<Dropdown options={[{ value: "a", label: "Alpha" }]} onChange={() => {}} />),
    );
    open();
    const trigger = container.querySelector('[role="combobox"]');
    expect(trigger.getAttribute("aria-activedescendant")).toBeTruthy();
    expect(document.querySelector('[role="listbox"]').hasAttribute("aria-activedescendant")).toBe(false);
  });
});
