// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import ExportDropdown from "../ExportDropdown";
import * as api from "../../../api";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

describe("ExportDropdown", () => {
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

  it("renders the trigger button and toggles the menu on click", () => {
    act(() => {
      root.render(<ExportDropdown fileId={1} artifactType="codebook" />);
    });

    const trigger = container.querySelector("button");
    expect(trigger.textContent).toContain("Export");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(container.querySelector('[role="menu"]')).toBeNull();

    act(() => {
      trigger.click();
    });

    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    const menu = container.querySelector('[role="menu"]');
    expect(menu).not.toBeNull();
    expect(menu.textContent).toContain("Codebook (.csv)");
  });

  it("displays accessible error state with role='alert' when export fails", async () => {
    vi.spyOn(api, "apiFetch").mockResolvedValue({
      ok: false,
      status: 500,
    });
    vi.spyOn(console, "error").mockImplementation(() => {});

    act(() => {
      root.render(<ExportDropdown fileId={1} artifactType="codebook" />);
    });

    // Open dropdown
    const trigger = container.querySelector("button");
    act(() => {
      trigger.click();
    });

    // Click the export option
    const csvOption = container.querySelectorAll('[role="menuitem"]')[0];
    await act(async () => {
      csvOption.click();
    });

    // Menu closes and accessible alert appears
    expect(container.querySelector('[role="menu"]')).toBeNull();
    const alert = container.querySelector('[role="alert"]');
    expect(alert).not.toBeNull();
    expect(alert.getAttribute("aria-live")).toBe("assertive");
    expect(alert.textContent).toContain("Export failed");

    // Dismiss error alert
    const dismissBtn = alert.querySelector("button");
    act(() => {
      dismissBtn.click();
    });
    expect(container.querySelector('[role="alert"]')).toBeNull();
  });

  it("clears the error state on a new dropdown toggle attempt", async () => {
    vi.spyOn(api, "apiFetch").mockRejectedValue(new Error("Network disconnect"));
    vi.spyOn(console, "error").mockImplementation(() => {});

    act(() => {
      root.render(<ExportDropdown fileId={1} artifactType="codebook" />);
    });

    const trigger = container.querySelector("button");
    act(() => {
      trigger.click();
    });

    const csvOption = container.querySelectorAll('[role="menuitem"]')[0];
    await act(async () => {
      csvOption.click();
    });

    expect(container.querySelector('[role="alert"]')).not.toBeNull();

    // Re-opening the dropdown clears the error
    act(() => {
      trigger.click();
    });

    expect(container.querySelector('[role="alert"]')).toBeNull();
  });
});
