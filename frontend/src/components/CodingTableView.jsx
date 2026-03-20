import React, { useMemo, useCallback } from "react";
import CodeLegend from "./CodeLegend";
import HighlightedContent from "./HighlightedContent";
import {
  getUniqueCodes,
  getFilteredCoding,
  getPostDataById,
} from "../lib/codingUtils";

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
          <table className="table">
            <thead>
              <tr>
                <th className="table__th">Post ID</th>
                <th className="table__th">Title</th>
                <th className="table__th">Content</th>
                <th className="table__th">Codes Applied</th>
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
                        <td
                          className="table__td"
                          style={{ verticalAlign: "top", maxWidth: "250px" }}
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
                        <td
                          className="table__td"
                          style={{ verticalAlign: "top", maxWidth: "125px" }}
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
                        <td
                          className="table__td"
                          style={{ verticalAlign: "top", maxWidth: "400px" }}
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
                        <td
                          className="table__td"
                          style={{ verticalAlign: "top", maxWidth: "175px" }}
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
                                  readOnlyCodeEvidence.map(({ code }) => code),
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
                            <span className="text-muted">No codes applied</span>
                          )}
                        </td>
                      </tr>

                      {isEditMode && (
                        <tr>
                          <td className="table__td" colSpan={4}>
                            <div
                              style={{
                                border: "1px solid rgba(255, 255, 255, 0.15)",
                                borderRadius: "6px",
                                padding: "12px",
                                backgroundColor: "rgba(255, 255, 255, 0.03)",
                              }}
                            >
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
