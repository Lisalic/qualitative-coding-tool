import React from "react";

// Component for the filterable code legend
const CodeLegend = ({
  codes,
  selectedFilterCodes,
  onCodeToggle,
  getCodeColor,
}) => {
  return (
    <div
      style={{
        marginBottom: "20px",
        padding: "10px",
        backgroundColor: "#222",
        borderRadius: "8px",
      }}
    >
      <h4 style={{ margin: "0 0 10px 0", color: "#fff" }}>Legend</h4>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
        {codes.map((code) => (
          <div
            key={code}
            onClick={() => onCodeToggle(code)}
            style={{
              display: "flex",
              alignItems: "center",
              backgroundColor: selectedFilterCodes.includes(code)
                ? "#555"
                : "#333",
              padding: "4px 8px",
              borderRadius: "4px",
              fontSize: "0.9em",
              cursor: "pointer",
              border: selectedFilterCodes.includes(code)
                ? "2px solid #fff"
                : "none",
              transition: "background-color 0.2s",
            }}
          >
            <div
              style={{
                width: "12px",
                height: "12px",
                backgroundColor: getCodeColor(code),
                borderRadius: "2px",
                marginRight: "6px",
                display: "inline-block",
                verticalAlign: "middle",
              }}
            />
            <span style={{ color: "#fff" }}>{code}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default CodeLegend;
