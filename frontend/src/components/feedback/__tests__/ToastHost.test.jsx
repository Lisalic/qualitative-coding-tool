// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import ToastHost from "../ToastHost";
import ToastService, { MAX_TOASTS, SHORT_TOAST_DURATION_MS, TOAST_DURATION_MS } from "../ToastService";

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

  it("shows an error toast with a countdown and removes it after the duration", () => {
    act(() => ToastService.show("Upload failed", "error"));
    expect(container.textContent).toContain("Upload failed");
    expect(container.textContent).toContain("Error");
    expect(container.textContent).toContain("15s");

    act(() => vi.advanceTimersByTime(5000));
    expect(container.textContent).toContain("10s");

    act(() => vi.advanceTimersByTime(TOAST_DURATION_MS));
    expect(container.textContent).not.toContain("Upload failed");
  });

  it("dismisses success notices sooner than errors", () => {
    act(() => ToastService.show("API Key saved!", "success"));
    expect(container.textContent).toContain("Success");
    expect(container.textContent).toContain(`${SHORT_TOAST_DURATION_MS / 1000}s`);
    act(() => vi.advanceTimersByTime(SHORT_TOAST_DURATION_MS));
    expect(container.textContent).not.toContain("API Key saved!");
  });

  it("keeps only the newest few toasts", () => {
    act(() => {
      for (let i = 0; i < MAX_TOASTS + 2; i += 1) ToastService.show(`Toast ${i}`);
    });
    expect(container.querySelectorAll('[role="status"]')).toHaveLength(MAX_TOASTS);
    expect(container.textContent).not.toContain("Toast 0");
    expect(container.textContent).toContain(`Toast ${MAX_TOASTS + 1}`);
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
