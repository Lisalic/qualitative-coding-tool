// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import ToastHost from "../ToastHost";
import ToastService, { TOAST_DURATION_MS } from "../ToastService";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

describe("ToastHost", () => {
  let container;
  let root;

  beforeEach(() => {
    vi.useFakeTimers();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    act(() => root.render(<ToastHost />));
  });

  afterEach(() => {
    ToastService.getSnapshot().forEach((toast) => ToastService.dismiss(toast.id));
    act(() => root.unmount());
    container.remove();
    vi.useRealTimers();
  });

  it("shows a toast with a countdown and removes it after the duration", () => {
    act(() => ToastService.show("API Key saved!", "success"));
    expect(container.textContent).toContain("API Key saved!");
    expect(container.textContent).toContain("Success");
    expect(container.textContent).toContain("15s");

    act(() => vi.advanceTimersByTime(5000));
    expect(container.textContent).toContain("10s");

    act(() => vi.advanceTimersByTime(TOAST_DURATION_MS));
    expect(container.textContent).not.toContain("API Key saved!");
  });

  it("dismisses on the × button", () => {
    act(() => ToastService.show("Failed to delete file.", "error"));
    const close = container.querySelector('button[aria-label="Dismiss"]');
    act(() => close.click());
    expect(container.textContent).not.toContain("Failed to delete file.");
  });

  it("stacks several toasts at once", () => {
    act(() => {
      ToastService.show("One");
      ToastService.show("Two");
    });
    expect(container.querySelectorAll('[role="status"]')).toHaveLength(2);
  });
});
