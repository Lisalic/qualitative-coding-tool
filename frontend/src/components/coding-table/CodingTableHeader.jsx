import React from "react";

const handleStyle = {
  position: "absolute",
  top: 0,
  right: "-2.5px",
  width: "5px",
  height: "100%",
  margin: 0,
  padding: 0,
  border: 0,
  background: "transparent",
  appearance: "none",
  cursor: "col-resize",
  zIndex: 20,
};

const handleLineStyle = {
  position: "absolute",
  top: 0,
  right: "2px",
  width: "1px",
  height: "100%",
  background: "#ffffff",
  opacity: 1,
  pointerEvents: "none",
};

const CodingTableHeader = ({
  visibleColumns,
  getColumnCellStyle,
  startColumnResize,
}) => {
  return (
    <thead>
      <tr>
        {visibleColumns.map(({ id, label }, index) => {
          const showResizer = index < visibleColumns.length - 1;
          const isLast = index === visibleColumns.length - 1;
          const rightColumnId = showResizer ? visibleColumns[index + 1].id : null;
          return (
            <th
              key={id}
              className={`relative select-none overflow-visible border-b-2 border-paper px-3 py-2.5 text-left font-medium ${
                isLast ? "" : "border-r"
              }`}
              style={getColumnCellStyle(id)}
            >
              <div className="pr-2">{label}</div>
              {!showResizer ? null : (
                <button
                  type="button"
                  role="separator"
                  aria-orientation="vertical"
                  aria-label={`Resize ${label} column`}
                  onPointerDown={(event) =>
                    startColumnResize(event, id, rightColumnId)
                  }
                  style={handleStyle}
                >
                  <span aria-hidden="true" style={handleLineStyle} />
                </button>
              )}
            </th>
          );
        })}
      </tr>
    </thead>
  );
};

export default CodingTableHeader;
