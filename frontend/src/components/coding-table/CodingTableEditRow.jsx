import React from "react";

const CodingTableEditRow = ({
  row,
  columnVisibility,
  visibleColumnCount,
  codeFieldOptions,
  saveStatus,
  updateRowPostId,
  updateRowCodeEvidenceField,
  removeRowCodeEvidence,
  addRowCodeEvidence,
}) => (
  <tr>
    <td className="table__td" colSpan={visibleColumnCount}>
      <div className="coding-table-edit-row">
        {!columnVisibility.postId && (
          <div className="form__group coding-table-edit-row__post-id">
            <label className="form__label">Post ID</label>
            <input
              type="text"
              className="form__input"
              value={row.editableItem?.postId || ""}
              onChange={(e) => updateRowPostId(row.sourceIndex, e.target.value)}
              disabled={saveStatus === "saving"}
            />
          </div>
        )}

        <div className="form__helper coding-table-edit-row__helper">
          Search code names by typing in the code field.
        </div>
        <datalist id={row.codeDatalistId}>
          {codeFieldOptions.map((codeOption) => (
            <option key={`${row.codeDatalistId}-${codeOption}`} value={codeOption} />
          ))}
        </datalist>

        <div className="coding-table-edit-row__entries">
          {row.editCodeEvidence.map((entry, entryIndex) => (
            <div
              key={`${row.rowKey}-entry-${entryIndex}`}
              className="coding-table-edit-row__entry"
            >
              <input
                type="text"
                list={row.codeDatalistId}
                className="form__input"
                placeholder="Search/select code"
                value={entry?.code || ""}
                onChange={(e) =>
                  updateRowCodeEvidenceField(
                    row.sourceIndex,
                    entryIndex,
                    "code",
                    e.target.value,
                  )
                }
                disabled={saveStatus === "saving"}
              />

              <textarea
                className="form__input"
                rows={2}
                placeholder="Evidence (use § or quotes for multiple snippets)"
                value={entry?.evidence || ""}
                onChange={(e) =>
                  updateRowCodeEvidenceField(
                    row.sourceIndex,
                    entryIndex,
                    "evidence",
                    e.target.value,
                  )
                }
                disabled={saveStatus === "saving"}
              />

              <textarea
                className="form__input"
                rows={2}
                placeholder="Researcher notes (shown on hover)"
                value={entry?.notes || ""}
                onChange={(e) =>
                  updateRowCodeEvidenceField(
                    row.sourceIndex,
                    entryIndex,
                    "notes",
                    e.target.value,
                  )
                }
                disabled={saveStatus === "saving"}
              />

              <button
                type="button"
                className="btn btn-secondary btn-small"
                onClick={() => removeRowCodeEvidence(row.sourceIndex, entryIndex)}
                disabled={saveStatus === "saving"}
              >
                Remove
              </button>
            </div>
          ))}

          <button
            type="button"
            className="btn btn-secondary btn-small coding-table-edit-row__add-btn"
            onClick={() => addRowCodeEvidence(row.sourceIndex)}
            disabled={saveStatus === "saving"}
          >
            + Add code/evidence
          </button>
        </div>
      </div>
    </td>
  </tr>
);

export default CodingTableEditRow;
