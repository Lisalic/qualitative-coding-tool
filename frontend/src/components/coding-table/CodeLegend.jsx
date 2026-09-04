import React, { useEffect, useMemo, useState, useRef, useCallback } from "react";
import { mintClientCodeUid } from "../../lib/codingUtils";
import { btnSm, inputSm } from "../../lib/uiClasses";

const btnSmall = btnSm;
const inputClasses = `min-w-0 ${inputSm}`;
const textareaClasses = `${inputClasses} min-h-[4.5rem] w-full resize-y`;

const DETAIL_FIELDS = [
  ["definition", "Definition"],
  ["inclusion", "Inclusion"],
  ["exclusion", "Exclusion"],
  ["keywords", "Keywords"],
  ["example", "Example"],
];

function codeDetailLines(code) {
  const lines = [];
  for (const [key, label] of DETAIL_FIELDS) {
    const value = typeof code?.[key] === "string" ? code[key].trim() : "";
    if (value) lines.push({ label, value });
  }
  return lines;
}

function extraFieldsFrom(entry) {
  return {
    body: typeof entry?.body === "string" ? entry.body : "",
    definition: entry?.definition ?? null,
    inclusion: entry?.inclusion ?? null,
    exclusion: entry?.exclusion ?? null,
    keywords: entry?.keywords ?? null,
    example: entry?.example ?? null,
  };
}

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
  showDetails = false,
}) => {
  const [expandedFamilies, setExpandedFamilies] = useState({});
  const [openMenuFamilyIndex, setOpenMenuFamilyIndex] = useState(null);
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
        const familyUid =
          typeof family?.family_uid === "string" && family.family_uid
            ? family.family_uid
            : `family-${familyIndex}`;

        const rawCodes = Array.isArray(family?.codes) ? family.codes : [];
        // Dedupe by code_uid (identity), not by name -- two distinct
        // codes can share a display name.
        const byUid = new Map();
        rawCodes.forEach((entry, codeIndex) => {
          const uid = typeof entry?.code_uid === "string" && entry.code_uid ? entry.code_uid : `code-${codeIndex}`;
          const name = typeof entry?.name === "string" && entry.name.trim() ? entry.name.trim() : `Code ${codeIndex + 1}`;
          if (!byUid.has(uid)) byUid.set(uid, { code_uid: uid, name, ...extraFieldsFrom(entry) });
        });

        return {
          familyUid,
          familyName,
          codes: Array.from(byUid.values()),
        };
      })
      .filter((family) => family.codes.length > 0);
  }, [codebookTree]);

  const hasTreeLegend = treeFamilies.length > 0;

  const editFamilies = useMemo(
    () => (Array.isArray(draftTree) ? draftTree : []),
    [draftTree],
  );

  const buildExpandedState = useMemo(() => {
    const initial = {};
    const list = isEditMode ? editFamilies : treeFamilies;
    list.forEach((_, index) => {
      initial[index] = true;
    });
    return initial;
  }, [isEditMode, editFamilies, treeFamilies]);

  // Reset only when the codebook or edit mode changes -- not when the
  // derived expand-map is recomputed. Depending on `buildExpandedState`
  // undid Expand All on the next render.
  useEffect(() => {
    if (isEditMode) {
      const list = Array.isArray(draftTree) ? draftTree : [];
      const initial = {};
      list.forEach((_, index) => {
        initial[index] = true;
      });
      setExpandedFamilies(initial);
      return;
    }
    setExpandedFamilies({});
    // draftTree is read only when entering edit mode; listing it would
    // re-expand on every keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditMode, codebookTree]);

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

  const handleCodeFieldChange = useCallback(
    (familyIndex, codeIndex, field, value) => {
      updateDraftTree((tree) =>
        tree.map((fam, fi) => {
          if (fi !== familyIndex) return fam;
          const codes = Array.isArray(fam.codes) ? [...fam.codes] : [];
          const next = codes.map((c, ci) =>
            ci === codeIndex ? { ...c, [field]: value } : c,
          );
          return { ...fam, codes: next };
        }),
      );
    },
    [updateDraftTree],
  );

  // Renaming a code here is just a `name` field edit -- `code_uid` stays
  // fixed, so nothing else needs to be notified: coding_entries reference
  // the uid, not the name, so a rename can never orphan an already-tagged
  // entry (unlike the old name-keyed codebook this replaces).

  const addFamily = useCallback(() => {
    // A client-minted uid (not "no uid until save") so a code added to
    // this brand-new family is immediately taggable in the reader pane
    // -- see useViewCodingPage's `availableCodes`, which reads from the
    // live draft, not the last-saved codebook.
    updateDraftTree((tree) => [
      ...tree,
      { family_uid: mintClientCodeUid(), family_is_new: true, family_name: "", codes: [] },
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
      // Same reasoning as addFamily: mint the uid now, not at save time,
      // so this code is immediately usable to tag a selection.
      updateDraftTree((tree) =>
        tree.map((fam, fi) => {
          if (fi !== familyIndex) return fam;
          const codes = Array.isArray(fam.codes) ? [...fam.codes] : [];
          codes.push({
            code_uid: mintClientCodeUid(),
            is_new: true,
            name: "",
            body: "",
            definition: "",
            inclusion: "",
            exclusion: "",
            keywords: "",
            example: "",
          });
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
    // Selection/filtering stays keyed on the display name (the server's
    // `?code=` row filter is name-based), while color and the toggle
    // payload carry `code_uid` -- the stable identity. The name row is
    // the click target so extra detail text doesn't toggle the filter.
    const isSelected = selectedCodeSet.has(code.name);
    const interactive = !disabled && typeof onCodeToggle === "function";
    const details = showDetails ? codeDetailLines(code) : [];
    const nameRow = (
      <>
        <div
          className="h-3 w-3 shrink-0"
          style={{ backgroundColor: getCodeColor(code.code_uid) }}
        />
        <span className={isSelected ? "font-semibold" : ""}>{code.name}</span>
      </>
    );
    if (!showDetails) {
      return (
        <div
          key={key}
          onClick={interactive ? () => onCodeToggle(code) : undefined}
          className={`flex items-center gap-1.5 px-2 py-1 text-sm transition-colors ${
            interactive ? "cursor-pointer" : "cursor-default"
          } ${
            isSelected
              ? "border-2 border-paper bg-white/10 font-semibold"
              : "border border-line-soft hover:bg-white/5"
          }`}
        >
          {nameRow}
        </div>
      );
    }
    return (
      <div
        key={key}
        className={
          isSelected
            ? "border-2 border-paper bg-white/10"
            : "border border-line-soft"
        }
      >
        <div
          onClick={interactive ? () => onCodeToggle(code) : undefined}
          className={`flex items-center gap-1.5 px-2 py-1 text-sm transition-colors ${
            interactive ? "cursor-pointer hover:bg-white/5" : "cursor-default"
          }`}
        >
          {nameRow}
        </div>
        {details.length > 0 && (
          <div className="flex flex-col gap-1 px-2 pb-2 pl-7 text-sm text-paper/80">
            {details.map((line) => (
              <div key={line.label} className="whitespace-pre-wrap">
                <span className="font-semibold text-paper/90">{line.label}: </span>
                {line.value}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  if (isEditMode) {
    return (
      <div className="w-full" ref={menuRootRef}>
        <div className="sticky top-0 z-[3] mb-2.5 flex flex-wrap gap-2 border-b border-line-soft bg-ink pb-2">
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
            className={`ml-auto ${btnSmall}`}
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
                <div key={`edit-family-${familyIndex}`} className="overflow-hidden border border-line">
                  <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2 border-b border-line-soft p-2">
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
                                typeof codeEntry?.name === "string" ? codeEntry.name : "";
                              const colorKey = codeEntry?.code_uid || `new-${familyIndex}-${codeIndex}`;
                              return (
                                <div
                                  key={`edit-code-${familyIndex}-${codeIndex}`}
                                  className="relative flex flex-col gap-1.5 bg-white/[0.03] py-1.5 pl-2 pr-1.5 before:absolute before:left-[-13px] before:top-4 before:w-2.5 before:border-t before:border-line-soft before:content-['']"
                                >
                                  <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-2">
                                    <div
                                      className="h-3 w-3 shrink-0"
                                      style={{
                                        backgroundColor: getCodeColor(colorKey),
                                      }}
                                    />
                                    <input
                                      type="text"
                                      className={inputClasses}
                                      value={cname}
                                      onChange={(e) =>
                                        handleCodeFieldChange(
                                          familyIndex,
                                          codeIndex,
                                          "name",
                                          e.target.value,
                                        )
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
                                  <div className="flex flex-col gap-1.5 pl-5">
                                    {DETAIL_FIELDS.map(([field, label]) => (
                                      <label key={field} className="flex flex-col gap-0.5">
                                        <span className="text-xs font-semibold uppercase tracking-wide text-paper/50">
                                          {label}
                                        </span>
                                        <textarea
                                          className={textareaClasses}
                                          value={typeof codeEntry?.[field] === "string" ? codeEntry[field] : ""}
                                          onChange={(e) =>
                                            handleCodeFieldChange(
                                              familyIndex,
                                              codeIndex,
                                              field,
                                              e.target.value,
                                            )
                                          }
                                          placeholder={label}
                                          disabled={disabled}
                                        />
                                      </label>
                                    ))}
                                  </div>
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
    <div className="w-full">
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
              <div key={family.familyUid} className="border border-line-soft">
                <div
                  onClick={() =>
                    setExpandedFamilies((prev) => ({
                      ...prev,
                      [index]: !prev[index],
                    }))
                  }
                  className="flex cursor-pointer items-center gap-2 border-b border-line-soft px-2 py-1.5 transition-colors hover:bg-white/5"
                >
                  <span className="w-4 text-center">
                    {expandedFamilies[index] ? "▾" : "▸"}
                  </span>
                  <strong className="text-sm">{family.familyName}</strong>
                </div>

                {expandedFamilies[index] && (
                  <div className="flex flex-col gap-1.5 p-2">
                    {family.codes.map((code) => renderCodeNode(code, code.code_uid))}
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
