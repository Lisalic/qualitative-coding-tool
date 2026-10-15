// @vitest-environment jsdom
import { expect, it } from "vitest";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { useUnmountSignal } from "../useUnmountSignal";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

it("aborts the signal when the component unmounts", () => {
  let getSignal;
  function Probe() {
    getSignal = useUnmountSignal();
    return null;
  }
  const root = createRoot(document.createElement("div"));
  act(() => root.render(<Probe />));

  const signal = getSignal();
  expect(signal.aborted).toBe(false);

  act(() => root.unmount());
  expect(signal.aborted).toBe(true);
});
