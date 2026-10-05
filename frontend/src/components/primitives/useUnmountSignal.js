import { useCallback, useEffect, useRef } from "react";

/**
 * Returns a getter for an `AbortSignal` that fires when the component
 * unmounts. Pass it to job polling (`postJsonAndPoll`/`postFormAndPoll`) so
 * leaving the page stops the polling instead of continuing for up to ten
 * minutes into a component that's gone. The job itself keeps running on
 * the server either way.
 */
export function useUnmountSignal() {
  const controllerRef = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    controllerRef.current = controller;
    return () => controller.abort();
  }, []);
  return useCallback(() => controllerRef.current?.signal, []);
}
