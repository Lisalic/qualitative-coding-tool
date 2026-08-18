import React, { useEffect, useId, useRef, useState } from "react";
import { TABLE_COLUMNS } from "./constants";

const ColumnPicker = ({
  columnVisibility,
  visibleColumnCount,
  toggleColumnVisibility,
}) => {
  const [columnPickerOpen, setColumnPickerOpen] = useState(false);
  const columnPickerRef = useRef(null);
  const columnPickerTriggerRef = useRef(null);
  const columnPickerPanelId = useId();
  const columnPickerHeadingId = useId();

  useEffect(() => {
    if (!columnPickerOpen) return undefined;
    const onPointerDown = (e) => {
      if (
        columnPickerRef.current &&
        !columnPickerRef.current.contains(e.target)
      ) {
        setColumnPickerOpen(false);
      }
    };
    const onKeyDown = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setColumnPickerOpen(false);
        columnPickerTriggerRef.current?.focus();
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [columnPickerOpen]);

  return (
    <div className="mb-3 flex justify-end">
      <div className="relative z-[5]" ref={columnPickerRef}>
        <button
          type="button"
          ref={columnPickerTriggerRef}
          className="inline-flex items-center border border-paper px-2.5 py-1 text-left text-xs font-semibold transition-colors hover:bg-paper hover:text-ink"
          aria-expanded={columnPickerOpen}
          aria-haspopup="true"
          aria-controls={columnPickerPanelId}
          onClick={() => setColumnPickerOpen((open) => !open)}
        >
          Hide/Show Columns
        </button>
        {!columnPickerOpen ? null : (
          <div
            id={columnPickerPanelId}
            className="absolute right-0 top-[calc(100%+6px)] min-w-[260px] max-w-[min(100vw-24px,320px)] border border-paper bg-ink p-3.5 shadow-lg"
            role="group"
            aria-labelledby={columnPickerHeadingId}
          >
            <div className="mb-2 text-sm font-semibold" id={columnPickerHeadingId}>
              Show Columns
            </div>
            <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
              {TABLE_COLUMNS.map(({ id, label }) => {
                const isLastVisible = columnVisibility[id] && visibleColumnCount === 1;
                return (
                  <li key={id}>
                    <label
                      className={`flex cursor-pointer select-none items-center gap-2.5 text-sm ${
                        isLastVisible ? "cursor-not-allowed opacity-85" : ""
                      }`}
                    >
                      <input
                        type="checkbox"
                        className="h-4 w-4 shrink-0 cursor-inherit accent-paper"
                        checked={columnVisibility[id]}
                        onChange={() => toggleColumnVisibility(id)}
                        disabled={isLastVisible}
                        title={
                          isLastVisible
                            ? "At least one column must remain visible."
                            : undefined
                        }
                      />
                      <span>{label}</span>
                    </label>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
};

export default ColumnPicker;
