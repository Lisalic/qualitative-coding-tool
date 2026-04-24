import { useCallback, useEffect, useRef } from "react";
import { clampColumnWidth, COLUMN_WIDTHS_MAX, COLUMN_WIDTHS_MIN } from "../constants";

export default function useColumnResize({
  columnWidths,
  setColumnWidths,
  setColumnWidthsAndPersist,
  onResizeStateChange,
}) {
  const resizeStateRef = useRef(null);
  const resizeCleanupRef = useRef(null);
  const frameRef = useRef(null);

  const commitColumnWidths = useCallback(
    (nextWidths) => {
      setColumnWidthsAndPersist((prev) => ({
        ...prev,
        ...nextWidths,
      }));
    },
    [setColumnWidthsAndPersist],
  );

  const startColumnResize = useCallback(
    (event, leftColumnId, rightColumnId) => {
      if (!leftColumnId || !rightColumnId) return;
      event.preventDefault();
      event.stopPropagation();
      const handleElement = event.currentTarget;
      const pointerId = event.pointerId;
      const startX = event.clientX;
      const leftStartWidth = clampColumnWidth(leftColumnId, columnWidths[leftColumnId]);
      const rightStartWidth = clampColumnWidth(rightColumnId, columnWidths[rightColumnId]);
      const totalWidth = leftStartWidth + rightStartWidth;
      resizeStateRef.current = {
        leftColumnId,
        rightColumnId,
        pointerId,
        startX,
        leftStartWidth,
        rightStartWidth,
        totalWidth,
      };
      onResizeStateChange?.(true);
      if (handleElement?.setPointerCapture) {
        handleElement.setPointerCapture(pointerId);
      }
      document.body.classList.add("column-resize-active");

      const onPointerMove = (moveEvent) => {
        const state = resizeStateRef.current;
        if (
          !state ||
          state.leftColumnId !== leftColumnId ||
          state.rightColumnId !== rightColumnId
        )
          return;

        const delta = moveEvent.clientX - state.startX;
        const leftMin = COLUMN_WIDTHS_MIN[leftColumnId] ?? 80;
        const leftMax = COLUMN_WIDTHS_MAX[leftColumnId] ?? 2000;
        const rightMin = COLUMN_WIDTHS_MIN[rightColumnId] ?? 80;
        const rightMax = COLUMN_WIDTHS_MAX[rightColumnId] ?? 2000;

        const feasibleLeftMin = Math.max(leftMin, state.totalWidth - rightMax);
        const feasibleLeftMax = Math.min(leftMax, state.totalWidth - rightMin);
        const unclampedLeft = state.leftStartWidth + delta;
        const nextLeftWidth = Math.min(
          feasibleLeftMax,
          Math.max(feasibleLeftMin, unclampedLeft),
        );
        const nextRightWidth = state.totalWidth - nextLeftWidth;

        if (frameRef.current) cancelAnimationFrame(frameRef.current);
        frameRef.current = requestAnimationFrame(() => {
          setColumnWidths((prev) => ({
            ...prev,
            [leftColumnId]: nextLeftWidth,
            [rightColumnId]: nextRightWidth,
          }));
          frameRef.current = null;
        });
      };

      const onPointerEnd = (endEvent) => {
        const state = resizeStateRef.current;
        if (
          !state ||
          state.leftColumnId !== leftColumnId ||
          state.rightColumnId !== rightColumnId
        )
          return;
        if (state.pointerId !== undefined && endEvent.pointerId !== state.pointerId)
          return;
        const delta = endEvent.clientX - state.startX;
        const leftMin = COLUMN_WIDTHS_MIN[leftColumnId] ?? 80;
        const leftMax = COLUMN_WIDTHS_MAX[leftColumnId] ?? 2000;
        const rightMin = COLUMN_WIDTHS_MIN[rightColumnId] ?? 80;
        const rightMax = COLUMN_WIDTHS_MAX[rightColumnId] ?? 2000;
        const feasibleLeftMin = Math.max(leftMin, state.totalWidth - rightMax);
        const feasibleLeftMax = Math.min(leftMax, state.totalWidth - rightMin);
        const finalLeft = Math.min(
          feasibleLeftMax,
          Math.max(feasibleLeftMin, state.leftStartWidth + delta),
        );
        const finalRight = state.totalWidth - finalLeft;
        // Persist exactly the two adjacent columns so total remains stable.
        commitColumnWidths({
          [leftColumnId]: finalLeft,
          [rightColumnId]: finalRight,
        });
        if (handleElement?.releasePointerCapture) {
          try {
            handleElement.releasePointerCapture(state.pointerId);
          } catch {
            // no-op: pointer may already be released
          }
        }
        resizeStateRef.current = null;
        resizeCleanupRef.current?.();
      };

      const cleanup = () => {
        document.body.classList.remove("column-resize-active");
        document.removeEventListener("pointermove", onPointerMove);
        document.removeEventListener("pointerup", onPointerEnd);
        document.removeEventListener("pointercancel", onPointerEnd);
        if (frameRef.current) {
          cancelAnimationFrame(frameRef.current);
          frameRef.current = null;
        }
        onResizeStateChange?.(false);
        if (resizeCleanupRef.current === cleanup) {
          resizeCleanupRef.current = null;
        }
      };

      resizeCleanupRef.current = cleanup;
      document.addEventListener("pointermove", onPointerMove);
      document.addEventListener("pointerup", onPointerEnd);
      document.addEventListener("pointercancel", onPointerEnd);
    },
    [columnWidths, commitColumnWidths, onResizeStateChange, setColumnWidths],
  );

  useEffect(() => {
    return () => {
      resizeCleanupRef.current?.();
      if (frameRef.current) cancelAnimationFrame(frameRef.current);
      document.body.classList.remove("column-resize-active");
    };
  }, []);

  return { startColumnResize, commitColumnWidths };
}
