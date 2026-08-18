import React from "react";

const inputClasses =
  "border border-paper bg-white/5 px-3 py-2 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";
const btnSmall =
  "border border-paper px-2.5 py-1 text-xs transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

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
    <td className="border-b border-paper/20 px-3 py-2.5" colSpan={visibleColumnCount}>
      <div className="border border-paper/15 bg-white/[0.03] p-3">
        {!columnVisibility.postId && (
          <div className="mb-3 flex flex-col gap-1.5">
            <label className="text-sm">Post ID</label>
            <input
              type="text"
              className={inputClasses}
              value={row.editableItem?.postId || ""}
              onChange={(e) => updateRowPostId(row.sourceIndex, e.target.value)}
              disabled={saveStatus === "saving"}
            />
          </div>
        )}

        <div className="mb-2 text-sm text-paper/60">
          Search code names by typing in the code field.
        </div>
        <datalist id={row.codeDatalistId}>
          {codeFieldOptions.map((codeOption) => (
            <option key={`${row.codeDatalistId}-${codeOption}`} value={codeOption} />
          ))}
        </datalist>

        <div className="flex flex-col gap-2">
          {row.editCodeEvidence.map((entry, entryIndex) => (
            <div
              key={`${row.rowKey}-entry-${entryIndex}`}
              className="grid grid-cols-[minmax(180px,1fr)_minmax(220px,2fr)_minmax(220px,1.6fr)_auto] items-start gap-2 border border-paper/15 p-2.5"
            >
              <input
                type="text"
                list={row.codeDatalistId}
                className={inputClasses}
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
                className={`${inputClasses} min-h-[68px] resize-y`}
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
                className={`${inputClasses} min-h-[68px] resize-y`}
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
                className={btnSmall}
                onClick={() => removeRowCodeEvidence(row.sourceIndex, entryIndex)}
                disabled={saveStatus === "saving"}
              >
                Remove
              </button>
            </div>
          ))}

          <button
            type="button"
            className={`${btnSmall} w-fit`}
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
