// @vitest-environment jsdom
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import useProjectPage from "../useProjectPage";
import * as api from "../../../api";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

function jsonResponse(body, ok = true) {
  return { ok, status: ok ? 200 : 500, json: async () => body };
}

let latest;
function Harness() {
  latest = useProjectPage("1");
  return null;
}

describe("useProjectPage", () => {
  let container;
  let root;

  beforeEach(() => {
    container = document.createElement("div");
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    vi.restoreAllMocks();
  });

  it("keeps the project on screen while refreshing (no loading flash)", async () => {
    const spy = vi
      .spyOn(api, "apiFetch")
      .mockResolvedValue(jsonResponse({ projects: [{ id: 1, projectname: "P" }] }));
    await act(async () => root.render(<Harness />));
    expect(latest.loading).toBe(false);
    expect(latest.project?.projectname).toBe("P");

    let refresh;
    act(() => {
      refresh = latest.refreshProject();
    });
    // Mid-refresh: still showing the project, not a loading screen.
    expect(latest.loading).toBe(false);
    expect(latest.project?.projectname).toBe("P");
    await act(async () => refresh);
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it("reports a failed load as an error, not as a missing project", async () => {
    vi.spyOn(api, "apiFetch").mockResolvedValue(jsonResponse({}, false));
    vi.spyOn(console, "error").mockImplementation(() => {});
    await act(async () => root.render(<Harness />));
    expect(latest.project).toBeNull();
    expect(latest.error).toMatch(/Couldn't load this project/);
  });
});
