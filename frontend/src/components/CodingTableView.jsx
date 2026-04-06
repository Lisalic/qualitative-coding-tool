import React, { useMemo, useCallback, useState } from "react";
import CodeLegend from "./CodeLegend";
import HighlightedContent from "./HighlightedContent";
import {
  getUniqueCodes,
  getFilteredCoding,
  getPostDataById,
} from "../lib/codingUtils";

const TABLE_COLUMN_STORAGE_KEY = "viewCoding.tableColumnVisibility";

const TABLE_COLUMNS = [
  { id: "postId", label: "Post ID" },
  { id: "title", label: "Title" },
  { id: "content", label: "Content" },
  { id: "codesApplied", label: "Codes Applied" },
];

const DEFAULT_COLUMN_VISIBILITY = {
  postId: false,
  title: true,
  content: true,
  codesApplied: true,
};

function readStoredColumnVisibility() {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(TABLE_COLUMN_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return null;
    const allowed = new Set(TABLE_COLUMNS.map((c) => c.id));
    const next = { ...DEFAULT_COLUMN_VISIBILITY };
    for (const [key, val] of Object.entries(parsed)) {
      if (allowed.has(key) && typeof val === "boolean") next[key] = val;
    }
    return next;
  } catch {
    return null;
  }
}

function normalizeColumnVisibility(raw) {
  const merged = {
    ...DEFAULT_COLUMN_VISIBILITY,
    ...(raw && typeof raw === "object" ? raw : {}),
  };
  const visibleCount = TABLE_COLUMNS.filter((c) => merged[c.id]).length;
  if (visibleCount === 0) return { ...DEFAULT_COLUMN_VISIBILITY };
  return merged;
}

// Component for the table view of coding data
const CodingTableView = ({
  parsedCoding,
  editableParsedCoding,
  isEditMode,
  onParsedCodingChange,
  codebookTree,
  postContents,
  selectedFilterCodes,
  setSelectedFilterCodes,
  getCodeColor,
  saveState,
}) => {
  const handleCodeToggle = useCallback(
    (code) => {
      setSelectedFilterCodes((prev) =>
        prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
      );
    },
    [setSelectedFilterCodes],
  );

  const uniqueCodes = useMemo(
    () => getUniqueCodes(parsedCoding),
    [parsedCoding],
  );

  const codebookCodes = useMemo(() => {
    if (!Array.isArray(codebookTree)) return [];

    const codes = [];
    codebookTree.forEach((family) => {
      const familyCodes = Array.isArray(family?.codes) ? family.codes : [];
      familyCodes.forEach((entry) => {
        if (typeof entry === "string" && entry.trim()) {
          codes.push(entry.trim());
          return;
        }
        if (entry && typeof entry.code_name === "string" && entry.code_name) {
          codes.push(entry.code_name.trim());
        }
      });
    });

    return Array.from(new Set(codes)).sort((a, b) => a.localeCompare(b));
  }, [codebookTree]);

  const codeFieldOptions = useMemo(
    () =>
      Array.from(
        new Set([...(uniqueCodes || []), ...(codebookCodes || [])]),
      ).sort((a, b) => a.localeCompare(b)),
    [uniqueCodes, codebookCodes],
  );

  const filteredCoding = useMemo(
    () =>
      isEditMode
        ? parsedCoding
        : getFilteredCoding(parsedCoding, selectedFilterCodes),
    [parsedCoding, selectedFilterCodes, isEditMode],
  );

  const rowsForRender = useMemo(
    () =>
      filteredCoding
        .map((item, filteredIndex) => {
          const sourceIndex = parsedCoding.indexOf(item);
          const editableItem =
            Array.isArray(editableParsedCoding) && sourceIndex >= 0
              ? editableParsedCoding[sourceIndex]
              : null;
          return {
            item,
            editableItem,
            sourceIndex,
            rowKey: `${sourceIndex}-${filteredIndex}`,
          };
        })
        .filter((row) => row.sourceIndex >= 0),
    [filteredCoding, parsedCoding, editableParsedCoding],
  );

  const updateRowPostId = useCallback(
    (sourceIndex, value) => {
      if (!isEditMode || typeof onParsedCodingChange !== "function") return;
      const currentRows = Array.isArray(editableParsedCoding)
        ? editableParsedCoding
        : [];
      onParsedCodingChange(
        currentRows.map((row, index) =>
          index === sourceIndex
            ? {
                ...row,
                postId: value,
              }
            : row,
        ),
      );
    },
    [isEditMode, onParsedCodingChange, editableParsedCoding],
  );

  const updateRowCodeEvidenceField = useCallback(
    (sourceIndex, entryIndex, field, value) => {
      if (!isEditMode || typeof onParsedCodingChange !== "function") return;
      const currentRows = Array.isArray(editableParsedCoding)
        ? editableParsedCoding
        : [];
      onParsedCodingChange(
        currentRows.map((row, index) => {
          if (index !== sourceIndex) return row;
          const nextCodeEvidence = (
            Array.isArray(row?.codeEvidence) ? row.codeEvidence : []
          ).map((entry, idx) =>
            idx === entryIndex ? { ...entry, [field]: value } : entry,
          );
          return {
            ...row,
            codeEvidence: nextCodeEvidence,
          };
        }),
      );
    },
    [isEditMode, onParsedCodingChange, editableParsedCoding],
  );

  const addRowCodeEvidence = useCallback(
    (sourceIndex) => {
      if (!isEditMode || typeof onParsedCodingChange !== "function") return;
      const currentRows = Array.isArray(editableParsedCoding)
        ? editableParsedCoding
        : [];
      onParsedCodingChange(
        currentRows.map((row, index) =>
          index === sourceIndex
            ? {
                ...row,
                codeEvidence: [
                  ...(Array.isArray(row?.codeEvidence) ? row.codeEvidence : []),
                  { code: "", evidence: "", notes: "" },
                ],
              }
            : row,
        ),
      );
    },
    [isEditMode, onParsedCodingChange, editableParsedCoding],
  );

  const removeRowCodeEvidence = useCallback(
    (sourceIndex, entryIndex) => {
      if (!isEditMode || typeof onParsedCodingChange !== "function") return;
      const currentRows = Array.isArray(editableParsedCoding)
        ? editableParsedCoding
        : [];
      onParsedCodingChange(
        currentRows.map((row, index) => {
          if (index !== sourceIndex) return row;
          const codeEvidence = Array.isArray(row?.codeEvidence)
            ? row.codeEvidence
            : [];
          return {
            ...row,
            codeEvidence: codeEvidence.filter((_, idx) => idx !== entryIndex),
          };
        }),
      );
    },
    [isEditMode, onParsedCodingChange, editableParsedCoding],
  );

  const [columnVisibility, setColumnVisibility] = useState(() =>
    normalizeColumnVisibility(readStoredColumnVisibility() || {}),
  );

  const visibleColumnCount = useMemo(
    () => TABLE_COLUMNS.filter((c) => columnVisibility[c.id]).length,
    [columnVisibility],
  );

  const toggleColumnVisibility = useCallback((columnId) => {
    setColumnVisibility((prev) => {
      const next = { ...prev, [columnId]: !prev[columnId] };
      const count = TABLE_COLUMNS.filter((c) => next[c.id]).length;
      if (count === 0) return prev;
      try {
        localStorage.setItem(TABLE_COLUMN_STORAGE_KEY, JSON.stringify(next));
      } catch {
        // ignore quota / private mode
      }
      return next;
    });
  }, []);

  return (
    <div>
      {saveState?.status === "saving" && (
        <div className="info-message" style={{ marginBottom: "10px" }}>
          Saving coding changes...
        </div>
      )}
      {saveState?.status === "error" && saveState?.message && (
        <div className="error-message" style={{ marginBottom: "10px" }}>
          {saveState.message}
        </div>
      )}
      {saveState?.status === "success" && saveState?.message && (
        <div className="success-message" style={{ marginBottom: "10px" }}>
          {saveState.message}
        </div>
      )}

      {selectedFilterCodes.length > 0 && !isEditMode && (
        <div className="body-sm text-primary" style={{ marginBottom: "10px" }}>
          <strong>Filtering by codes:</strong> {selectedFilterCodes.join(", ")}{" "}
          <button
            onClick={() => setSelectedFilterCodes([])}
            className="btn btn-secondary btn-small"
          >
            Clear Filter
          </button>
        </div>
      )}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(260px, 320px) minmax(0, 1fr)",
          gap: "16px",
          alignItems: "start",
        }}
      >
        <CodeLegend
          codes={uniqueCodes}
          codebookTree={codebookTree}
          selectedFilterCodes={selectedFilterCodes}
          onCodeToggle={handleCodeToggle}
          getCodeColor={getCodeColor}
        />

        <div className="table-wrapper">
          <div
            className="body-sm text-primary"
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              gap: "12px 16px",
              marginBottom: "12px",
            }}
          >
            <span style={{ fontWeight: 600 }}>Columns</span>
            {TABLE_COLUMNS.map(({ id, label }) => (
              <label
                key={id}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  cursor:
                    columnVisibility[id] && visibleColumnCount === 1
                      ? "not-allowed"
                      : "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={columnVisibility[id]}
                  onChange={() => toggleColumnVisibility(id)}
                  disabled={columnVisibility[id] && visibleColumnCount === 1}
                />
                {label}
              </label>
            ))}
          </div>
          <table className="table">
            <thead>
              <tr>
                {TABLE_COLUMNS.map(({ id, label }) =>
                  columnVisibility[id] ? (
                    <th key={id} className="table__th">
                      {label}
                    </th>
                  ) : null,
                )}
              </tr>
            </thead>
            <tbody>
              {rowsForRender.map(
                ({ item, editableItem, sourceIndex, rowKey }) => {
                  const readOnlyCodeEvidence =
                    !isEditMode && selectedFilterCodes.length > 0
                      ? item.codeEvidence.filter((ev) =>
                          selectedFilterCodes.includes(ev.code),
                        )
                      : item.codeEvidence;

                  const editCodeEvidence = Array.isArray(
                    editableItem?.codeEvidence,
                  )
                    ? editableItem.codeEvidence
                    : [];

                  const notesByCode = readOnlyCodeEvidence.reduce(
                    (acc, entry) => {
                      const code = String(entry?.code || "").trim();
                      const notes = String(entry?.notes || "").trim();
                      if (!code || !notes) return acc;
                      if (!acc[code]) acc[code] = new Set();
                      acc[code].add(notes);
                      return acc;
                    },
                    {},
                  );

                  const postData = getPostDataById(postContents, item.postId);
                  const postTitle = postData?.title || "Title not found";
                  const postContent = postData?.content;
                  const codeDatalistId = `code-options-${rowKey}`;
                  const editCodes = Array.from(
                    new Set(
                      editCodeEvidence
                        .map((entry) => String(entry?.code || "").trim())
                        .filter(Boolean),
                    ),
                  );

                  return (
                    <React.Fragment key={rowKey}>
                      <tr className="table__row--hover">
                        {columnVisibility.postId && (
                          <td
                            className="table__td"
                            style={{
                              verticalAlign: "top",
                              maxWidth: "250px",
                            }}
                          >
                            {isEditMode ? (
                              <input
                                type="text"
                                className="form__input"
                                value={editableItem?.postId || ""}
                                onChange={(e) =>
                                  updateRowPostId(sourceIndex, e.target.value)
                                }
                                disabled={saveState?.status === "saving"}
                              />
                            ) : (
                              item.postId
                            )}
                          </td>
                        )}
                        {columnVisibility.title && (
                          <td
                            className="table__td"
                            style={{
                              verticalAlign: "top",
                              maxWidth: "125px",
                            }}
                          >
                            <div
                              style={{
                                whiteSpace: "pre-wrap",
                                wordWrap: "break-word",
                              }}
                            >
                              {postTitle}
                            </div>
                          </td>
                        )}
                        {columnVisibility.content && (
                          <td
                            className="table__td"
                            style={{
                              verticalAlign: "top",
                              maxWidth: "400px",
                            }}
                          >
                            <div
                              style={{
                                whiteSpace: "pre-wrap",
                                wordWrap: "break-word",
                              }}
                            >
                              {postContent ? (
                                <div
                                  style={{
                                    whiteSpace: "pre-wrap",
                                    wordWrap: "break-word",
                                  }}
                                >
                                  <HighlightedContent
                                    content={postContent}
                                    codeEvidence={readOnlyCodeEvidence}
                                    getCodeColor={getCodeColor}
                                  />
                                </div>
                              ) : (
                                "Content not found"
                              )}
                            </div>
                          </td>
                        )}
                        {columnVisibility.codesApplied && (
                          <td
                            className="table__td"
                            style={{
                              verticalAlign: "top",
                              maxWidth: "175px",
                            }}
                          >
                            {isEditMode ? (
                              <div>
                                {editCodes.length > 0 ? (
                                  editCodes.map((code) => (
                                    <div
                                      key={`${rowKey}-edit-code-${code}`}
                                      className="code-badge-container"
                                    >
                                      <div
                                        className="code-badge"
                                        style={{
                                          backgroundColor: getCodeColor(code),
                                        }}
                                      >
                                        {code}
                                      </div>
                                    </div>
                                  ))
                                ) : (
                                  <span className="text-muted">
                                    No codes configured
                                  </span>
                                )}
                              </div>
                            ) : readOnlyCodeEvidence.length > 0 ? (
                              <div>
                                {[
                                  ...new Set(
                                    readOnlyCodeEvidence.map(
                                      ({ code }) => code,
                                    ),
                                  ),
                                ].map((code) => {
                                  const notesForCode = notesByCode[code]
                                    ? Array.from(notesByCode[code])
                                    : [];

                                  return (
                                    <div
                                      key={code}
                                      className="code-badge-container"
                                    >
                                      <div
                                        className="code-badge"
                                        data-has-notes={
                                          notesForCode.length > 0
                                            ? "true"
                                            : "false"
                                        }
                                        style={{
                                          backgroundColor: getCodeColor(code),
                                        }}
                                      >
                                        {code}
                                      </div>

                                      {notesForCode.length > 0 && (
                                        <div
                                          className="code-notes-tooltip"
                                          role="tooltip"
                                        >
                                          <div className="code-notes-tooltip__title">
                                            Researcher Notes
                                          </div>
                                          {notesForCode.map((note, idx) => (
                                            <div
                                              key={`${code}-note-${idx}`}
                                              className="code-notes-tooltip__line"
                                            >
                                              {note}
                                            </div>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  );
                                })}
                              </div>
                            ) : (
                              <span className="text-muted">
                                No codes applied
                              </span>
                            )}
                          </td>
                        )}
                      </tr>

                      {isEditMode && (
                        <tr>
                          <td
                            className="table__td"
                            colSpan={visibleColumnCount}
                          >
                            <div
                              style={{
                                border: "1px solid rgba(255, 255, 255, 0.15)",
                                borderRadius: "6px",
                                padding: "12px",
                                backgroundColor: "rgba(255, 255, 255, 0.03)",
                              }}
                            >
                              {!columnVisibility.postId && (
                                <div
                                  className="form__group"
                                  style={{ marginBottom: "12px" }}
                                >
                                  <label className="form__label">Post ID</label>
                                  <input
                                    type="text"
                                    className="form__input"
                                    value={editableItem?.postId || ""}
                                    onChange={(e) =>
                                      updateRowPostId(
                                        sourceIndex,
                                        e.target.value,
                                      )
                                    }
                                    disabled={saveState?.status === "saving"}
                                  />
                                </div>
                              )}
                              <div
                                className="form__helper"
                                style={{ marginTop: 0 }}
                              >
                                Search code names by typing in the code field.
                              </div>
                              <datalist id={codeDatalistId}>
                                {codeFieldOptions.map((codeOption) => (
                                  <option
                                    key={`${codeDatalistId}-${codeOption}`}
                                    value={codeOption}
                                  />
                                ))}
                              </datalist>

                              <div
                                style={{
                                  display: "flex",
                                  flexDirection: "column",
                                  gap: "8px",
                                }}
                              >
                                {editCodeEvidence.map((entry, entryIndex) => (
                                  <div
                                    key={`${rowKey}-entry-${entryIndex}`}
                                    style={{
                                      border:
                                        "1px solid rgba(255, 255, 255, 0.15)",
                                      borderRadius: "6px",
                                      padding: "10px",
                                      display: "grid",
                                      gridTemplateColumns:
                                        "minmax(180px, 1fr) minmax(220px, 2fr) minmax(220px, 1.6fr) auto",
                                      gap: "8px",
                                      alignItems: "start",
                                    }}
                                  >
                                    <input
                                      type="text"
                                      list={codeDatalistId}
                                      className="form__input"
                                      placeholder="Search/select code"
                                      value={entry?.code || ""}
                                      onChange={(e) =>
                                        updateRowCodeEvidenceField(
                                          sourceIndex,
                                          entryIndex,
                                          "code",
                                          e.target.value,
                                        )
                                      }
                                      disabled={saveState?.status === "saving"}
                                    />

                                    <textarea
                                      className="form__input"
                                      rows={2}
                                      placeholder="Evidence (use § or quotes for multiple snippets)"
                                      value={entry?.evidence || ""}
                                      onChange={(e) =>
                                        updateRowCodeEvidenceField(
                                          sourceIndex,
                                          entryIndex,
                                          "evidence",
                                          e.target.value,
                                        )
                                      }
                                      disabled={saveState?.status === "saving"}
                                      style={{
                                        resize: "vertical",
                                        minHeight: "68px",
                                      }}
                                    />

                                    <textarea
                                      className="form__input"
                                      rows={2}
                                      placeholder="Researcher notes (shown on hover)"
                                      value={entry?.notes || ""}
                                      onChange={(e) =>
                                        updateRowCodeEvidenceField(
                                          sourceIndex,
                                          entryIndex,
                                          "notes",
                                          e.target.value,
                                        )
                                      }
                                      disabled={saveState?.status === "saving"}
                                      style={{
                                        resize: "vertical",
                                        minHeight: "68px",
                                      }}
                                    />

                                    <button
                                      type="button"
                                      className="btn btn-secondary btn-small"
                                      onClick={() =>
                                        removeRowCodeEvidence(
                                          sourceIndex,
                                          entryIndex,
                                        )
                                      }
                                      disabled={saveState?.status === "saving"}
                                    >
                                      Remove
                                    </button>
                                  </div>
                                ))}

                                <button
                                  type="button"
                                  className="btn btn-secondary btn-small"
                                  onClick={() =>
                                    addRowCodeEvidence(sourceIndex)
                                  }
                                  disabled={saveState?.status === "saving"}
                                  style={{ width: "fit-content" }}
                                >
                                  + Add code/evidence
                                </button>
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                },
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default CodingTableView;
