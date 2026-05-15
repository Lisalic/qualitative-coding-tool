import React from "react";
import HighlightedContent from "./HighlightedContent";

const CodingTableRow = ({
  row,
  visibleColumns,
  getColumnCellStyle,
  getCodeColor,
}) => {
  const uniqueCodes = [...new Set(row.readOnlyCodeEvidence.map(({ code }) => code))];
  const lastColumnIndex = visibleColumns.length - 1;

  const getBodyCellStyle = (columnId, index) => ({
    ...getColumnCellStyle(columnId),
    borderRight: index < lastColumnIndex ? "1px solid #ffffff" : "none",
  });

  return (
    <tr className="table__row--hover">
      {visibleColumns.map(({ id }, index) => {
        if (id === "postId") {
          return (
            <td key={`${row.rowKey}-postId`} className="table__td" style={getBodyCellStyle("postId", index)}>
              {row.item.postId}
            </td>
          );
        }

        if (id === "title") {
          return (
            <td key={`${row.rowKey}-title`} className="table__td" style={getBodyCellStyle("title", index)}>
              <div className="table__cell-wrap">{row.postTitle}</div>
            </td>
          );
        }

        if (id === "content") {
          return (
            <td
              key={`${row.rowKey}-content`}
              className="table__td table__td--content"
              style={getBodyCellStyle("content", index)}
            >
              <div className="table__cell-wrap">
                {row.postContent ? (
                  <div className="table__cell-wrap">
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
              className="table__td table__td--codes"
              style={getBodyCellStyle("codesApplied", index)}
            >
              {row.readOnlyCodeEvidence.length > 0 ? (
                <div className="table__codes-wrap">
                  {uniqueCodes.map((code) => {
                    const notesForCode = row.notesByCode[code]
                      ? Array.from(row.notesByCode[code])
                      : [];

                    return (
                      <div key={code} className="code-badge-container">
                        <div
                          className="code-badge"
                          data-has-notes={notesForCode.length > 0 ? "true" : "false"}
                          style={{ backgroundColor: getCodeColor(code) }}
                        >
                          {code}
                        </div>
                        {notesForCode.length > 0 && (
                          <div className="code-notes-tooltip" role="tooltip">
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
          );
        }

        return null;
      })}
    </tr>
  );
};

export default CodingTableRow;
