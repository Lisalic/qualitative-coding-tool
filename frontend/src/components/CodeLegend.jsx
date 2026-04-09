import React, { useEffect, useMemo, useState, useRef, useCallback } from "react";

// Component for the filterable code legend (read-only) and editable codebook (table edit mode)
const CodeLegend = ({
  codebookTree,
  selectedFilterCodes,
  onCodeToggle,
  getCodeColor,
  isEditMode = false,
  draftTree,
  onDraftTreeChange,
  disabled = false,
  onCodingRowCodeRename,
}) => {
  const [expandedFamilies, setExpandedFamilies] = useState({});
  const codeNameSnapshotRef = useRef({});

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

  const editFamilies = Array.isArray(draftTree) ? draftTree : [];

  const buildExpandedState = useMemo(() => {
    const initial = {};
    const list = isEditMode ? editFamilies : treeFamilies;
    list.forEach((_, index) => {
      initial[index] = true;
    });
    return initial;
  }, [isEditMode, editFamilies, treeFamilies]);

  useEffect(() => {
    if (isEditMode) {
      setExpandedFamilies(buildExpandedState);
      return;
    }
    if (!hasTreeLegend) {
      setExpandedFamilies({});
      return;
    }
    setExpandedFamilies(buildExpandedState);
  }, [isEditMode, hasTreeLegend, buildExpandedState]);

  const updateDraftTree = useCallback(
    (updater) => {
      if (typeof onDraftTreeChange !== "function") return;
      const base = Array.isArray(draftTree) ? draftTree : [];
      onDraftTreeChange(updater(base));
    },
    [draftTree, onDraftTreeChange],
  );

  const handleFamilyNameChange = useCallback(
    (familyIndex, value) => {
      updateDraftTree((tree) =>
        tree.map((fam, i) =>
          i === familyIndex
            ? { ...fam, family_name: value, codes: fam.codes || [] }
            : fam,
        ),
      );
    },
    [updateDraftTree],
  );

  const handleCodeNameChange = useCallback(
    (familyIndex, codeIndex, value) => {
      updateDraftTree((tree) =>
        tree.map((fam, fi) => {
          if (fi !== familyIndex) return fam;
          const codes = Array.isArray(fam.codes) ? [...fam.codes] : [];
          const next = codes.map((c, ci) =>
            ci === codeIndex ? { ...c, code_name: value } : c,
          );
          return { ...fam, codes: next };
        }),
      );
    },
    [updateDraftTree],
  );

  const handleCodeNameFocus = useCallback((familyIndex, codeIndex) => {
    const key = `${familyIndex}-${codeIndex}`;
    const tree = Array.isArray(draftTree) ? draftTree : [];
    const name = (tree[familyIndex]?.codes?.[codeIndex]?.code_name || "").trim();
    codeNameSnapshotRef.current[key] = name;
  }, [draftTree]);

  const handleCodeNameBlur = useCallback(
    (familyIndex, codeIndex) => {
      const key = `${familyIndex}-${codeIndex}`;
      const tree = Array.isArray(draftTree) ? draftTree : [];
      const start = codeNameSnapshotRef.current[key] ?? "";
      const end = (tree[familyIndex]?.codes?.[codeIndex]?.code_name || "").trim();
      if (
        start &&
        start !== end &&
        typeof onCodingRowCodeRename === "function"
      ) {
        onCodingRowCodeRename(start, end);
      }
      codeNameSnapshotRef.current[key] = end;
    },
    [draftTree, onCodingRowCodeRename],
  );

  const addFamily = useCallback(() => {
    updateDraftTree((tree) => [
      ...tree,
      { family_name: "New code family", content: "", codes: [] },
    ]);
  }, [updateDraftTree]);

  const removeFamily = useCallback(
    (familyIndex) => {
      updateDraftTree((tree) => tree.filter((_, i) => i !== familyIndex));
    },
    [updateDraftTree],
  );

  const addCode = useCallback(
    (familyIndex) => {
      updateDraftTree((tree) =>
        tree.map((fam, fi) => {
          if (fi !== familyIndex) return fam;
          const codes = Array.isArray(fam.codes) ? [...fam.codes] : [];
          codes.push({ code_name: "", content: "" });
          return { ...fam, codes };
        }),
      );
    },
    [updateDraftTree],
  );

  const removeCode = useCallback(
    (familyIndex, codeIndex) => {
      updateDraftTree((tree) =>
        tree.map((fam, fi) => {
          if (fi !== familyIndex) return fam;
          const codes = Array.isArray(fam.codes) ? fam.codes : [];
          return {
            ...fam,
            codes: codes.filter((_, ci) => ci !== codeIndex),
          };
        }),
      );
    },
    [updateDraftTree],
  );

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

  const shellStyle = {
    padding: "10px",
    backgroundColor: "#222",
    borderRadius: "8px",
    width: "100%",
  };

  if (isEditMode) {
    return (
      <div style={shellStyle}>
        <h4 style={{ margin: "0 0 10px 0", color: "#fff" }}>Codebook</h4>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            gap: "8px",
            marginBottom: "8px",
            flexWrap: "wrap",
          }}
        >
          <button
            type="button"
            onClick={() => setExpandedFamilies(buildExpandedState)}
            className="db-button"
            style={{ padding: "4px 8px", fontSize: "0.8rem" }}
            disabled={disabled}
          >
            Expand All
          </button>
          <button
            type="button"
            onClick={() => setExpandedFamilies({})}
            className="db-button"
            style={{ padding: "4px 8px", fontSize: "0.8rem" }}
            disabled={disabled}
          >
            Collapse All
          </button>
          <button
            type="button"
            onClick={addFamily}
            className="btn btn-secondary btn-small"
            disabled={disabled}
          >
            + Add code family
          </button>
        </div>

        {editFamilies.length === 0 ? (
          <div style={{ color: "#bbbbbb", fontSize: "0.9rem" }}>
            No code families yet. Use &quot;Add code family&quot; to start.
          </div>
        ) : (
          <div
            style={{ display: "flex", flexDirection: "column", gap: "8px" }}
          >
            {editFamilies.map((family, familyIndex) => {
              const famName =
                typeof family?.family_name === "string"
                  ? family.family_name
                  : "";
              const codes = Array.isArray(family?.codes) ? family.codes : [];
              return (
                <div
                  key={`edit-family-${familyIndex}`}
                  style={{ border: "1px solid #333", borderRadius: "6px" }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "6px 8px",
                      backgroundColor: "#111",
                      flexWrap: "wrap",
                    }}
                  >
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedFamilies((prev) => ({
                          ...prev,
                          [familyIndex]: !prev[familyIndex],
                        }))
                      }
                      className="db-button"
                      style={{
                        padding: "2px 6px",
                        fontSize: "0.75rem",
                        minWidth: "28px",
                      }}
                      disabled={disabled}
                    >
                      {expandedFamilies[familyIndex] ? "▾" : "▸"}
                    </button>
                    <input
                      type="text"
                      className="form__input"
                      style={{ flex: "1 1 140px", minWidth: "120px" }}
                      value={famName}
                      onChange={(e) =>
                        handleFamilyNameChange(familyIndex, e.target.value)
                      }
                      placeholder="Family name"
                      disabled={disabled}
                    />
                    <button
                      type="button"
                      className="btn btn-secondary btn-small"
                      onClick={() => addCode(familyIndex)}
                      disabled={disabled}
                    >
                      + Code
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-small"
                      onClick={() => removeFamily(familyIndex)}
                      disabled={disabled}
                    >
                      Remove family
                    </button>
                  </div>

                  {expandedFamilies[familyIndex] && (
                    <div
                      style={{
                        padding: "8px",
                        display: "flex",
                        flexDirection: "column",
                        gap: "8px",
                      }}
                    >
                      {codes.length === 0 ? (
                        <span className="text-muted body-sm">
                          No codes in this family yet.
                        </span>
                      ) : (
                        codes.map((codeEntry, codeIndex) => {
                          const cname =
                            typeof codeEntry?.code_name === "string"
                              ? codeEntry.code_name
                              : "";
                          const displayCode = cname.trim() || "(unnamed)";
                          return (
                            <div
                              key={`edit-code-${familyIndex}-${codeIndex}`}
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "8px",
                                flexWrap: "wrap",
                              }}
                            >
                              <div
                                style={{
                                  width: "12px",
                                  height: "12px",
                                  backgroundColor: getCodeColor(displayCode),
                                  borderRadius: "2px",
                                  flexShrink: 0,
                                }}
                              />
                              <input
                                type="text"
                                className="form__input"
                                style={{
                                  flex: "1 1 160px",
                                  minWidth: "140px",
                                }}
                                value={cname}
                                onChange={(e) =>
                                  handleCodeNameChange(
                                    familyIndex,
                                    codeIndex,
                                    e.target.value,
                                  )
                                }
                                onFocus={() =>
                                  handleCodeNameFocus(familyIndex, codeIndex)
                                }
                                onBlur={() =>
                                  handleCodeNameBlur(familyIndex, codeIndex)
                                }
                                placeholder="Code name"
                                disabled={disabled}
                              />
                              <button
                                type="button"
                                className="btn btn-secondary btn-small"
                                onClick={() =>
                                  removeCode(familyIndex, codeIndex)
                                }
                                disabled={disabled}
                              >
                                Remove
                              </button>
                            </div>
                          );
                        })
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={shellStyle}>
      <h4 style={{ margin: "0 0 10px 0", color: "#fff" }}>Codes</h4>

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
