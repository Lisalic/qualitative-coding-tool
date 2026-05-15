import React from "react";

const baseHeaderStyle = {
  position: "relative",
  userSelect: "none",
  overflow: "visible",
  borderRight: "1px solid #ffffff",
};

const headerContentStyle = {
  paddingRight: "8px",
};

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
              className="table__th table__th--resizable"
              style={{
                ...getColumnCellStyle(id),
                ...baseHeaderStyle,
                borderRight: isLast ? "none" : "1px solid #ffffff",
              }}
            >
              <div style={headerContentStyle}>{label}</div>
              {!showResizer ? null : (
                <button
                  type="button"
                  className="table__column-resizer"
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
