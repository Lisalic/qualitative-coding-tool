import React, { useEffect, useId, useRef, useState } from "react";
import { TABLE_COLUMNS } from "../constants";

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
    <div className="column-picker-toolbar">
      <div className="column-picker" ref={columnPickerRef}>
        <button
          type="button"
          ref={columnPickerTriggerRef}
          className="btn btn-secondary btn-small column-picker__trigger"
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
            className="column-picker__panel"
            role="group"
            aria-labelledby={columnPickerHeadingId}
          >
            <div className="column-picker__title" id={columnPickerHeadingId}>
              Show Columns
            </div>
            <ul className="column-picker__list">
              {TABLE_COLUMNS.map(({ id, label }) => {
                const isLastVisible = columnVisibility[id] && visibleColumnCount === 1;
                return (
                  <li key={id} className="column-picker__row">
                    <label
                      className={`column-picker__label${isLastVisible ? " column-picker__label--disabled" : ""}`}
                    >
                      <input
                        type="checkbox"
                        className="column-picker__checkbox"
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
