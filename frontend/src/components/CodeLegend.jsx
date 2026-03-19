import React, { useEffect, useMemo, useState } from "react";

// Component for the filterable code legend
const CodeLegend = ({
  codebookTree,
  selectedFilterCodes,
  onCodeToggle,
  getCodeColor,
}) => {
  const [expandedFamilies, setExpandedFamilies] = useState({});

  const selectedCodeSet = useMemo(
    () => new Set(selectedFilterCodes || []),
    [selectedFilterCodes],
  );

  const treeFamilies = useMemo(() => {
    if (!Array.isArray(codebookTree)) return [];

    return codebookTree
      .map((family, familyIndex) => {
        const familyName =
          typeof family?.family_name === "string" && family.family_name.trim()
            ? family.family_name.trim()
            : `Family ${familyIndex + 1}`;

        const rawCodes = Array.isArray(family?.codes) ? family.codes : [];
        const normalizedCodes = rawCodes
          .map((entry, codeIndex) => {
            if (typeof entry === "string") return entry.trim();
            if (
              entry &&
              typeof entry.code_name === "string" &&
              entry.code_name.trim()
            ) {
              return entry.code_name.trim();
            }
            return `Code ${codeIndex + 1}`;
          })
          .filter(Boolean);

        return {
          familyName,
          codes: Array.from(new Set(normalizedCodes)),
        };
      })
      .filter((family) => family.codes.length > 0);
  }, [codebookTree]);

  const hasTreeLegend = treeFamilies.length > 0;

  const buildExpandedState = useMemo(() => {
    const initial = {};
    treeFamilies.forEach((_, index) => {
      initial[index] = true;
    });
    return initial;
  }, [treeFamilies]);

  useEffect(() => {
    if (!hasTreeLegend) {
      setExpandedFamilies({});
      return;
    }
    setExpandedFamilies(buildExpandedState);
  }, [hasTreeLegend, buildExpandedState]);

  const renderCodeNode = (code, key) => {
    const isSelected = selectedCodeSet.has(code);
    return (
      <div
        key={key}
        onClick={() => onCodeToggle(code)}
        style={{
          display: "flex",
          alignItems: "center",
          backgroundColor: isSelected ? "#555" : "#333",
          padding: "4px 8px",
          borderRadius: "4px",
          fontSize: "0.9em",
          cursor: "pointer",
          border: isSelected ? "2px solid #fff" : "none",
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
    );
  };

  return (
    <div
      style={{
        padding: "10px",
        backgroundColor: "#222",
        borderRadius: "8px",
        width: "100%",
      }}
    >
      <h4 style={{ margin: "0 0 10px 0", color: "#fff" }}>Legend</h4>

      {hasTreeLegend ? (
        <div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: "8px",
              marginBottom: "8px",
            }}
          >
            <button
              type="button"
              onClick={() => setExpandedFamilies(buildExpandedState)}
              className="db-button"
              style={{ padding: "4px 8px", fontSize: "0.8rem" }}
            >
              Expand All
            </button>
            <button
              type="button"
              onClick={() => setExpandedFamilies({})}
              className="db-button"
              style={{ padding: "4px 8px", fontSize: "0.8rem" }}
            >
              Collapse All
            </button>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {treeFamilies.map((family, index) => (
              <div
                key={`${family.familyName}-${index}`}
                style={{ border: "1px solid #333", borderRadius: "6px" }}
              >
                <div
                  onClick={() =>
                    setExpandedFamilies((prev) => ({
                      ...prev,
                      [index]: !prev[index],
                    }))
                  }
                  style={{
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "6px 8px",
                    backgroundColor: "#111",
                  }}
                >
                  <span style={{ width: "16px", textAlign: "center" }}>
                    {expandedFamilies[index] ? "▾" : "▸"}
                  </span>
                  <strong style={{ color: "#fff", fontSize: "0.9rem" }}>
                    {family.familyName}
                  </strong>
                </div>

                {expandedFamilies[index] && (
                  <div
                    style={{
                      padding: "8px",
                      display: "flex",
                      flexDirection: "column",
                      gap: "6px",
                    }}
                  >
                    {family.codes.map((code) =>
                      renderCodeNode(code, `${family.familyName}-${code}`),
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div style={{ color: "#bbbbbb", fontSize: "0.9rem" }}>
          codebook not found
        </div>
      )}
    </div>
  );
};

export default CodeLegend;
