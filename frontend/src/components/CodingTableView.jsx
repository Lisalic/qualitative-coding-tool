import React, { useMemo, useCallback, useState } from "react";
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
  codebookTree,
  postContents,
  selectedFilterCodes,
  setSelectedFilterCodes,
  getCodeColor,
  onSaveParsedCoding,
  saveState,
}) => {
  const [editingSourceIndex, setEditingSourceIndex] = useState(null);
  const [draftPostId, setDraftPostId] = useState("");
  const [draftCodeEvidence, setDraftCodeEvidence] = useState([]);
  const [rowError, setRowError] = useState("");
  const [isSavingRow, setIsSavingRow] = useState(false);

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
    () => getFilteredCoding(parsedCoding, selectedFilterCodes),
    [parsedCoding, selectedFilterCodes],
  );

  const rowsForRender = useMemo(
    () =>
      filteredCoding
        .map((item, filteredIndex) => {
          const sourceIndex = parsedCoding.indexOf(item);
          return {
            item,
            sourceIndex,
            rowKey: `${sourceIndex}-${filteredIndex}`,
          };
        })
        .filter((row) => row.sourceIndex >= 0),
    [filteredCoding, parsedCoding],
  );

  const resetEditorState = useCallback(() => {
    setEditingSourceIndex(null);
    setDraftPostId("");
    setDraftCodeEvidence([]);
    setRowError("");
    setIsSavingRow(false);
  }, []);

  const startRowEdit = useCallback((sourceIndex, item) => {
    setEditingSourceIndex(sourceIndex);
    setDraftPostId(item?.postId || "");
    setDraftCodeEvidence(
      Array.isArray(item?.codeEvidence)
        ? item.codeEvidence.map((entry) => ({
            code: entry?.code || "",
            evidence: entry?.evidence || "",
            notes: entry?.notes || "",
          }))
        : [],
    );
    setRowError("");
  }, []);

  const updateDraftEntry = useCallback((index, field, value) => {
    setDraftCodeEvidence((prev) =>
      prev.map((entry, entryIndex) =>
        entryIndex === index ? { ...entry, [field]: value } : entry,
      ),
    );
  }, []);

  const removeDraftEntry = useCallback((index) => {
    setDraftCodeEvidence((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const addDraftEntry = useCallback(() => {
    setDraftCodeEvidence((prev) => [
      ...prev,
      { code: "", evidence: "", notes: "" },
    ]);
  }, []);

  const handleSaveEntry = useCallback(async () => {
    if (editingSourceIndex === null) return;

    const normalizedPostId = String(draftPostId || "").trim();
    const normalizedCodeEvidence = draftCodeEvidence
      .map((entry) => ({
        code: String(entry?.code || "").trim(),
        evidence: String(entry?.evidence || "").trim(),
        notes: String(entry?.notes || "").trim(),
      }))
      .filter((entry) => entry.code && entry.evidence)
      .map((entry) =>
        entry.notes
          ? entry
          : {
              code: entry.code,
              evidence: entry.evidence,
            },
      );

    if (!normalizedPostId) {
      setRowError("Post ID is required.");
      return;
    }

    if (normalizedCodeEvidence.length === 0) {
      setRowError("Add at least one code with evidence before saving.");
      return;
    }

    if (typeof onSaveParsedCoding !== "function") {
      setRowError("Save handler is unavailable.");
      return;
    }

    const nextParsedCoding = parsedCoding.map((row, index) =>
      index === editingSourceIndex
        ? {
            postId: normalizedPostId,
            codeEvidence: normalizedCodeEvidence,
          }
        : row,
    );

    setIsSavingRow(true);
    setRowError("");

    try {
      const result = await onSaveParsedCoding(nextParsedCoding);
      if (result?.ok) {
        resetEditorState();
        return;
      }
      setRowError(result?.error || "Failed to save entry.");
    } catch (error) {
      setRowError(error?.message || "Failed to save entry.");
    } finally {
      setIsSavingRow(false);
    }
  }, [
    editingSourceIndex,
    draftPostId,
    draftCodeEvidence,
    onSaveParsedCoding,
    parsedCoding,
    resetEditorState,
  ]);

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

      {selectedFilterCodes.length > 0 && (
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
                <th className="table__th" style={{ width: "130px" }}>
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {rowsForRender.map(({ item, sourceIndex, rowKey }) => {
                const filteredCodeEvidence =
                  selectedFilterCodes.length > 0
                    ? item.codeEvidence.filter((ev) =>
                        selectedFilterCodes.includes(ev.code),
                      )
                    : item.codeEvidence;

                const notesByCode = filteredCodeEvidence.reduce(
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
                const isEditingThisRow = editingSourceIndex === sourceIndex;
                const codeDatalistId = `code-options-${rowKey}`;

                return (
                  <React.Fragment key={rowKey}>
                    <tr
                      className="table__row--hover"
                      style={
                        isEditingThisRow
                          ? { backgroundColor: "rgba(255, 255, 255, 0.05)" }
                          : undefined
                      }
                    >
                      <td
                        className="table__td"
                        style={{ verticalAlign: "top", maxWidth: "250px" }}
                      >
                        {item.postId}
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
                                codeEvidence={filteredCodeEvidence}
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
                        {filteredCodeEvidence.length > 0 ? (
                          <div>
                            {[
                              ...new Set(
                                filteredCodeEvidence.map(({ code }) => code),
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
                                      notesForCode.length > 0 ? "true" : "false"
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
                      <td
                        className="table__td"
                        style={{ verticalAlign: "top" }}
                      >
                        <button
                          type="button"
                          className="btn btn-secondary btn-small"
                          onClick={() => startRowEdit(sourceIndex, item)}
                          disabled={isSavingRow}
                        >
                          {isEditingThisRow ? "Editing" : "Edit Entry"}
                        </button>
                      </td>
                    </tr>

                    {isEditingThisRow && (
                      <tr>
                        <td className="table__td" colSpan={5}>
                          <div
                            style={{
                              border: "1px solid rgba(255, 255, 255, 0.2)",
                              borderRadius: "6px",
                              padding: "12px",
                              backgroundColor: "rgba(255, 255, 255, 0.03)",
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                marginBottom: "10px",
                              }}
                            >
                              <strong>Edit Entry</strong>
                              <span className="text-muted">{item.postId}</span>
                            </div>

                            <div
                              className="form__group"
                              style={{ marginBottom: "12px" }}
                            >
                              <label className="form__label">Post ID</label>
                              <input
                                type="text"
                                className="form__input"
                                value={draftPostId}
                                onChange={(e) => setDraftPostId(e.target.value)}
                                disabled={isSavingRow}
                              />
                            </div>

                            <div className="form__group">
                              <label className="form__label">
                                Codes and Evidence
                              </label>
                              <div className="form__helper">
                                Search code names by typing in the code
                                dropdown.
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
                                {draftCodeEvidence.map((entry, draftIndex) => (
                                  <div
                                    key={`${rowKey}-entry-${draftIndex}`}
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
                                      value={entry.code}
                                      onChange={(e) =>
                                        updateDraftEntry(
                                          draftIndex,
                                          "code",
                                          e.target.value,
                                        )
                                      }
                                      disabled={isSavingRow}
                                    />
                                    <textarea
                                      className="form__input"
                                      rows={2}
                                      placeholder="Evidence (use § or quotes for multiple snippets)"
                                      value={entry.evidence}
                                      onChange={(e) =>
                                        updateDraftEntry(
                                          draftIndex,
                                          "evidence",
                                          e.target.value,
                                        )
                                      }
                                      disabled={isSavingRow}
                                      style={{
                                        resize: "vertical",
                                        minHeight: "68px",
                                      }}
                                    />
                                    <textarea
                                      className="form__input"
                                      rows={2}
                                      placeholder="Researcher notes (shown on hover)"
                                      value={entry.notes || ""}
                                      onChange={(e) =>
                                        updateDraftEntry(
                                          draftIndex,
                                          "notes",
                                          e.target.value,
                                        )
                                      }
                                      disabled={isSavingRow}
                                      style={{
                                        resize: "vertical",
                                        minHeight: "68px",
                                      }}
                                    />
                                    <button
                                      type="button"
                                      className="btn btn-secondary btn-small"
                                      onClick={() =>
                                        removeDraftEntry(draftIndex)
                                      }
                                      disabled={isSavingRow}
                                    >
                                      Remove
                                    </button>
                                  </div>
                                ))}

                                <button
                                  type="button"
                                  className="btn btn-secondary btn-small"
                                  onClick={addDraftEntry}
                                  disabled={isSavingRow}
                                  style={{ width: "fit-content" }}
                                >
                                  + Add code/evidence
                                </button>
                              </div>
                            </div>

                            {rowError && (
                              <div
                                className="error-message"
                                style={{ marginTop: "10px" }}
                              >
                                {rowError}
                              </div>
                            )}

                            <div
                              style={{
                                display: "flex",
                                gap: "8px",
                                marginTop: "12px",
                              }}
                            >
                              <button
                                type="button"
                                className="btn btn-primary btn-small"
                                onClick={handleSaveEntry}
                                disabled={isSavingRow}
                              >
                                {isSavingRow ? "Saving..." : "Save Entry"}
                              </button>
                              <button
                                type="button"
                                className="btn btn-secondary btn-small"
                                onClick={resetEditorState}
                                disabled={isSavingRow}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default CodingTableView;
