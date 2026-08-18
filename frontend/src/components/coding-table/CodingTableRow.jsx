import React from "react";
import HighlightedContent from "./HighlightedContent";

const tdClasses = "border-b border-r border-paper/20 px-3 py-2.5 last:border-r-0";

const CodingTableRow = ({
  row,
  visibleColumns,
  getColumnCellStyle,
  getCodeColor,
}) => {
  const uniqueCodes = [...new Set(row.readOnlyCodeEvidence.map(({ code }) => code))];

  return (
    <tr className="transition-colors hover:bg-white/5">
      {visibleColumns.map(({ id }) => {
        if (id === "postId") {
          return (
            <td
              key={`${row.rowKey}-postId`}
              className={tdClasses}
              style={getColumnCellStyle("postId")}
            >
              {row.item.postId}
            </td>
          );
        }

        if (id === "title") {
          return (
            <td
              key={`${row.rowKey}-title`}
              className={tdClasses}
              style={getColumnCellStyle("title")}
            >
              <div className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
                {row.postTitle}
              </div>
            </td>
          );
        }

        if (id === "content") {
          return (
            <td
              key={`${row.rowKey}-content`}
              className={`${tdClasses} min-w-0`}
              style={getColumnCellStyle("content")}
            >
              <div className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
                {row.postContent ? (
                  <div className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
                    <HighlightedContent
                      content={row.postContent}
                      codeEvidence={row.readOnlyCodeEvidence}
                      getCodeColor={getCodeColor}
                    />
                  </div>
                ) : (
                  "Content not found"
                )}
              </div>
            </td>
          );
        }

        if (id === "codesApplied") {
          return (
            <td
              key={`${row.rowKey}-codesApplied`}
              className={`${tdClasses} min-w-0 overflow-hidden`}
              style={getColumnCellStyle("codesApplied")}
            >
              {row.readOnlyCodeEvidence.length > 0 ? (
                <div className="flex min-w-0 flex-wrap gap-1 overflow-hidden">
                  {uniqueCodes.map((code) => {
                    const notesForCode = row.notesByCode[code]
                      ? Array.from(row.notesByCode[code])
                      : [];
                    const hasNotes = notesForCode.length > 0;

                    return (
                      <div
                        key={code}
                        className="group relative m-0.5 inline-flex min-w-0 max-w-full items-center"
                      >
                        <div
                          className={`inline-block max-w-full truncate px-2 py-1 text-sm font-bold text-ink ${
                            hasNotes
                              ? "cursor-help shadow-[inset_0_0_0_1px_rgba(255,255,255,0.75)]"
                              : ""
                          }`}
                          style={{ backgroundColor: getCodeColor(code) }}
                        >
                          {code}
                        </div>
                        {hasNotes && (
                          <div
                            role="tooltip"
                            className="invisible absolute left-1/2 top-[calc(100%+8px)] z-[60] w-max min-w-[220px] max-w-[340px] -translate-x-1/2 border border-paper bg-ink px-2.5 py-2 text-sm leading-snug text-paper opacity-0 shadow-lg transition-opacity group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100"
                          >
                            <div className="mb-1 text-xs uppercase tracking-wide text-paper/60">
                              Researcher Notes
                            </div>
                            {notesForCode.map((note, idx) => (
                              <div key={`${code}-note-${idx}`}>{note}</div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <span className="text-paper/60">No codes applied</span>
              )}
            </td>
          );
        }

        return null;
      })}
    </tr>
  );
};

export default CodingTableRow;
