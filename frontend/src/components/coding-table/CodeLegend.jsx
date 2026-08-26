import React, { useEffect, useMemo, useState, useRef, useCallback } from "react";

const btnSmall =
  "border border-paper px-2.5 py-1 text-xs transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";
const inputClasses =
  "min-w-0 border border-paper bg-white/5 px-2 py-1 text-sm text-paper focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";

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
      // Editing benefits from seeing everything at once -- expanded by
      // default there, unlike the read-only view below.
      setExpandedFamilies(buildExpandedState);
      return;
    }
    // Collapsed by default in the read-only view -- a codebook can have
    // many families, and a researcher is usually here to read/tag a
    // document, not browse the whole codebook. Expanding is a deliberate
    // action (a family row, or "Expand All").
    setExpandedFamilies({});
  }, [isEditMode, buildExpandedState]);

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
        className={`flex cursor-pointer items-center gap-1.5 px-2 py-1 text-sm transition-colors ${
          isSelected
            ? "border-2 border-paper bg-white/10 font-semibold"
            : "border border-paper/20 hover:bg-white/5"
        }`}
      >
        <div
          className="h-3 w-3 shrink-0"
          style={{ backgroundColor: getCodeColor(code) }}
        />
        <span>{code}</span>
      </div>
    );
  };

  if (isEditMode) {
    return (
      <div className="w-full border border-paper p-3" ref={menuRootRef}>
        <h4 className="mb-2.5 font-semibold">Codebook</h4>
        <div className="sticky top-0 z-[3] mb-2.5 flex flex-wrap gap-2 border-b border-paper/20 bg-ink pb-2">
          <button
            type="button"
            onClick={() => setExpandedFamilies(buildExpandedState)}
            className={btnSmall}
            disabled={disabled}
          >
            Expand all
          </button>
          <button
            type="button"
            onClick={() => setExpandedFamilies({})}
            className={btnSmall}
            disabled={disabled}
          >
            Collapse all
          </button>
          <button
            type="button"
            onClick={addFamily}
            className="ml-auto border-2 border-paper px-2.5 py-1 text-xs font-semibold transition-colors hover:bg-paper hover:text-ink disabled:opacity-40"
            disabled={disabled}
          >
            + Add family
          </button>
        </div>

        {editFamilies.length === 0 ? (
          <div className="px-0.5 py-2 text-sm text-paper/60">
            No code families yet. Use &quot;Add family&quot; to start.
          </div>
        ) : (
          <div className="flex flex-col gap-2.5">
            {editFamilies.map((family, familyIndex) => {
              const famName =
                typeof family?.family_name === "string"
                  ? family.family_name
                  : "";
              const codes = Array.isArray(family?.codes) ? family.codes : [];
              const isMenuOpen = openMenuFamilyIndex === familyIndex;
              const isExpanded = Boolean(expandedFamilies[familyIndex]);

              return (
                <div key={`edit-family-${familyIndex}`} className="overflow-hidden border border-paper/30">
                  <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 border-b border-paper/20 p-2">
                    <div className="flex items-center gap-1.5">
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedFamilies((prev) => ({
                            ...prev,
                            [familyIndex]: !prev[familyIndex],
                          }))
                        }
                        className="min-w-[28px] border border-paper px-1.5 py-0.5 text-xs transition-colors hover:bg-paper hover:text-ink disabled:opacity-40"
                        disabled={disabled}
                        aria-label={isExpanded ? "Collapse family" : "Expand family"}
                      >
                        {isExpanded ? "▾" : "▸"}
                      </button>
                    </div>
                    <input
                      type="text"
                      className={inputClasses}
                      value={famName}
                      onChange={(e) =>
                        handleFamilyNameChange(familyIndex, e.target.value)
                      }
                      placeholder="Code family name"
                      disabled={disabled}
                    />

                    <div className="relative">
                      <button
                        type="button"
                        className="min-w-[30px] border border-paper px-2 py-0.5 text-base leading-none transition-colors hover:bg-paper hover:text-ink disabled:opacity-40"
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
                        <div
                          className="absolute right-0 top-[calc(100%+6px)] z-[5] min-w-[150px] border border-paper bg-ink p-1 shadow-lg"
                          role="menu"
                        >
                          <button
                            type="button"
                            className="block w-full px-2 py-1.5 text-left text-sm transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
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
                            className="block w-full px-2 py-1.5 text-left text-sm text-error transition-colors hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
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
                    <div className="flex flex-col gap-2.5 p-2.5 pl-3">
                      {codes.length === 0 ? (
                        <span className="text-sm text-paper/70">
                          No codes in this family yet.
                        </span>
                      ) : (
                        <div className="flex flex-col gap-2">
                          <div className="pl-[18px] text-xs font-semibold uppercase tracking-wide text-paper/50">
                            Codes
                          </div>
                          <div className="relative flex flex-col gap-1.5 pl-[18px] before:absolute before:bottom-0.5 before:left-[5px] before:top-0.5 before:w-px before:bg-paper/20 before:content-['']">
                            {codes.map((codeEntry, codeIndex) => {
                              const cname =
                                typeof codeEntry?.code_name === "string"
                                  ? codeEntry.code_name
                                  : "";
                              const displayCode = cname.trim() || "(unnamed)";
                              return (
                                <div
                                  key={`edit-code-${familyIndex}-${codeIndex}`}
                                  className="relative grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 bg-white/[0.03] py-1.5 pl-2 pr-1.5 before:absolute before:left-[-13px] before:top-1/2 before:w-2.5 before:border-t before:border-paper/20 before:content-['']"
                                >
                                  <div
                                    className="h-3 w-3 shrink-0"
                                    style={{
                                      backgroundColor: getCodeColor(displayCode),
                                    }}
                                  />
                                  <input
                                    type="text"
                                    className={inputClasses}
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
                                    className="min-w-[28px] border border-paper px-1.5 py-0.5 text-sm leading-none transition-colors hover:bg-paper hover:text-ink disabled:opacity-40"
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
    <div className="w-full border border-paper p-3">
      <h4 className="mb-2.5 font-semibold">Codes</h4>

      {hasTreeLegend ? (
        <div>
          <div className="mb-2 flex justify-between gap-2">
            <button
              type="button"
              onClick={() => setExpandedFamilies(buildExpandedState)}
              className={btnSmall}
            >
              Expand All
            </button>
            <button
              type="button"
              onClick={() => setExpandedFamilies({})}
              className={btnSmall}
            >
              Collapse All
            </button>
          </div>

          <div className="flex flex-col gap-2">
            {treeFamilies.map((family, index) => (
              <div key={`${family.familyName}-${index}`} className="border border-paper/20">
                <div
                  onClick={() =>
                    setExpandedFamilies((prev) => ({
                      ...prev,
                      [index]: !prev[index],
                    }))
                  }
                  className="flex cursor-pointer items-center gap-2 border-b border-paper/20 px-2 py-1.5 transition-colors hover:bg-white/5"
                >
                  <span className="w-4 text-center">
                    {expandedFamilies[index] ? "▾" : "▸"}
                  </span>
                  <strong className="text-sm">{family.familyName}</strong>
                </div>

                {expandedFamilies[index] && (
                  <div className="flex flex-col gap-1.5 p-2">
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
        <div className="text-sm text-paper/70">codebook not found</div>
      )}
    </div>
  );
};

export default CodeLegend;
