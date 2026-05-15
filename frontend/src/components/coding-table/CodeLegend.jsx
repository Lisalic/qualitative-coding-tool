import React, { useEffect, useMemo, useState, useRef, useCallback } from "react";
import "../../styles/CodeLegend.css";

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
  const [openMenuFamilyIndex, setOpenMenuFamilyIndex] = useState(null);
  const codeNameSnapshotRef = useRef({});
  const menuRootRef = useRef(null);

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

  useEffect(() => {
    if (!isEditMode) {
      setOpenMenuFamilyIndex(null);
      return;
    }

    const onPointerDown = (event) => {
      if (!menuRootRef.current?.contains(event.target)) {
        setOpenMenuFamilyIndex(null);
      }
    };

    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        setOpenMenuFamilyIndex(null);
      }
    };

    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [isEditMode]);

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
      { family_name: "", content: "", codes: [] },
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
      <div style={shellStyle} className="code-legend code-legend--edit" ref={menuRootRef}>
        <h4 className="code-legend__title">Codebook</h4>
        <div className="code-legend__toolbar">
          <button
            type="button"
            onClick={() => setExpandedFamilies(buildExpandedState)}
            className="db-button code-legend__toolbar-btn"
            disabled={disabled}
          >
            Expand all
          </button>
          <button
            type="button"
            onClick={() => setExpandedFamilies({})}
            className="db-button code-legend__toolbar-btn"
            disabled={disabled}
          >
            Collapse all
          </button>
          <button
            type="button"
            onClick={addFamily}
            className="btn btn-secondary btn-small code-legend__toolbar-btn code-legend__toolbar-btn--primary"
            disabled={disabled}
          >
            + Add family
          </button>
        </div>

        {editFamilies.length === 0 ? (
          <div className="code-legend__empty-state">
            No code families yet. Use &quot;Add family&quot; to start.
          </div>
        ) : (
          <div className="code-legend__family-list">
            {editFamilies.map((family, familyIndex) => {
              const famName =
                typeof family?.family_name === "string"
                  ? family.family_name
                  : "";
              const codes = Array.isArray(family?.codes) ? family.codes : [];
              const isMenuOpen = openMenuFamilyIndex === familyIndex;
              const isExpanded = Boolean(expandedFamilies[familyIndex]);

              return (
                <div key={`edit-family-${familyIndex}`} className="code-legend__family-card">
                  <div className="code-legend__family-header">
                    <div className="code-legend__family-meta">
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedFamilies((prev) => ({
                            ...prev,
                            [familyIndex]: !prev[familyIndex],
                          }))
                        }
                        className="db-button code-legend__toggle"
                        disabled={disabled}
                        aria-label={isExpanded ? "Collapse family" : "Expand family"}
                      >
                        {isExpanded ? "▾" : "▸"}
                      </button>
                    </div>
                    <input
                      type="text"
                      className="form__input code-legend__family-input"
                      value={famName}
                      onChange={(e) =>
                        handleFamilyNameChange(familyIndex, e.target.value)
                      }
                      placeholder="Code family name"
                      disabled={disabled}
                    />

                    <div className="code-legend__menu-wrap">
                      <button
                        type="button"
                        className="db-button code-legend__menu-trigger"
                        onClick={() =>
                          setOpenMenuFamilyIndex((prev) =>
                            prev === familyIndex ? null : familyIndex,
                          )
                        }
                        disabled={disabled}
                        aria-haspopup="menu"
                        aria-expanded={isMenuOpen}
                        aria-label="Family actions"
                      >
                        ⋯
                      </button>
                      {isMenuOpen && (
                        <div className="code-legend__menu" role="menu">
                          <button
                            type="button"
                            className="code-legend__menu-item"
                            onClick={() => {
                              addCode(familyIndex);
                              setOpenMenuFamilyIndex(null);
                            }}
                            disabled={disabled}
                          >
                            + Add code
                          </button>
                          <button
                            type="button"
                            className="code-legend__menu-item code-legend__menu-item--danger"
                            onClick={() => {
                              removeFamily(familyIndex);
                              setOpenMenuFamilyIndex(null);
                            }}
                            disabled={disabled}
                          >
                            Remove family
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="code-legend__family-body">
                      {codes.length === 0 ? (
                        <span className="text-muted body-sm">
                          No codes in this family yet.
                        </span>
                      ) : (
                        <div className="code-legend__codes-section">
                          <div className="code-legend__codes-label">Codes</div>
                          <div className="code-legend__codes-tree">
                            {codes.map((codeEntry, codeIndex) => {
                              const cname =
                                typeof codeEntry?.code_name === "string"
                                  ? codeEntry.code_name
                                  : "";
                              const displayCode = cname.trim() || "(unnamed)";
                              return (
                                <div
                                  key={`edit-code-${familyIndex}-${codeIndex}`}
                                  className="code-legend__code-row"
                                >
                                  <div
                                    className="code-legend__code-color"
                                    style={{
                                      backgroundColor: getCodeColor(displayCode),
                                    }}
                                  />
                                  <input
                                    type="text"
                                    className="form__input code-legend__code-input"
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
                                    className="db-button code-legend__remove-code"
                                    onClick={() =>
                                      removeCode(familyIndex, codeIndex)
                                    }
                                    disabled={disabled}
                                    aria-label="Remove code"
                                    title="Remove code"
                                  >
                                    ×
                                  </button>
                                </div>
                              );
                            })}
                          </div>
                        </div>
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
