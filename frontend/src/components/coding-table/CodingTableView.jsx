import React, { useCallback, useEffect, useRef } from "react";
import CodeLegend from "./CodeLegend";
import HighlightedContent from "./HighlightedContent";
import ColumnPicker from "./ColumnPicker";
import CodingTableHeader from "./CodingTableHeader";
import CodingTableRow from "./CodingTableRow";
import CodingTableEditRow from "./CodingTableEditRow";
import useColumnSettings from "./useColumnSettings";
import useColumnResize from "./useColumnResize";
import useCodingTableData from "./useCodingTableData";
import {
  COLUMN_WIDTHS_MAX,
  COLUMN_WIDTHS_MIN,
} from "./constants";

function fitVisibleColumnsToWidth(visibleIds, sourceWidths, targetWidth) {
  if (!Array.isArray(visibleIds) || visibleIds.length === 0 || targetWidth <= 0) {
    return null;
  }

  const widths = {};
  let sourceTotal = 0;
  visibleIds.forEach((id) => {
    const width = Math.max(COLUMN_WIDTHS_MIN[id] ?? 80, Number(sourceWidths[id]) || 0);
    widths[id] = width;
    sourceTotal += width;
  });

  if (sourceTotal <= 0) return null;
  const scale = targetWidth / sourceTotal;
  visibleIds.forEach((id) => {
    const min = COLUMN_WIDTHS_MIN[id] ?? 80;
    const max = COLUMN_WIDTHS_MAX[id] ?? 2000;
    widths[id] = Math.min(max, Math.max(min, widths[id] * scale));
  });

  // Small correction pass to keep the sum equal to targetWidth.
  let sum = visibleIds.reduce((acc, id) => acc + widths[id], 0);
  let diff = targetWidth - sum;
  const epsilon = 0.5;
  let guard = 0;
  while (Math.abs(diff) > epsilon && guard < 40) {
    guard += 1;
    const adjustable = visibleIds.filter((id) => {
      const min = COLUMN_WIDTHS_MIN[id] ?? 80;
      const max = COLUMN_WIDTHS_MAX[id] ?? 2000;
      return diff > 0 ? widths[id] < max : widths[id] > min;
    });
    if (adjustable.length === 0) break;
    const step = diff / adjustable.length;
    adjustable.forEach((id) => {
      const min = COLUMN_WIDTHS_MIN[id] ?? 80;
      const max = COLUMN_WIDTHS_MAX[id] ?? 2000;
      widths[id] = Math.min(max, Math.max(min, widths[id] + step));
    });
    sum = visibleIds.reduce((acc, id) => acc + widths[id], 0);
    diff = targetWidth - sum;
  }

  return widths;
}

// Component for the table view of coding data
const CodingTableView = ({
  parsedCoding,
  editableParsedCoding,
  isEditMode,
  onParsedCodingChange,
  codebookTree,
  editableCodebookTree,
  onEditableCodebookTreeChange,
  onCodingRowCodeRename,
  postContents,
  selectedFilterCodes,
  setSelectedFilterCodes,
  getCodeColor,
  saveState,
}) => {
  const isResizingRef = useRef(false);
  const latestWidthsRef = useRef({});
  const handleCodeToggle = useCallback(
    (code) => {
      setSelectedFilterCodes((prev) =>
        prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
      );
    },
    [setSelectedFilterCodes],
  );

  const {
    columnVisibility,
    columnWidths,
    setColumnWidths,
    setColumnWidthsAndPersist,
    visibleColumns,
    visibleColumnCount,
    toggleColumnVisibility,
    getColumnCellStyle,
  } = useColumnSettings();

  const { startColumnResize } = useColumnResize({
    columnWidths,
    setColumnWidths,
    setColumnWidthsAndPersist,
    onResizeStateChange: (isResizing) => {
      isResizingRef.current = isResizing;
    },
  });
  const tableWrapperRef = useRef(null);

  useEffect(() => {
    latestWidthsRef.current = columnWidths;
  }, [columnWidths]);

  const {
    codeFieldOptions,
    rowsForRender,
    updateRowPostId,
    updateRowCodeEvidenceField,
    addRowCodeEvidence,
    appendCodeEvidenceWithText,
    removeRowCodeEvidence,
  } = useCodingTableData({
    parsedCoding,
    editableParsedCoding,
    isEditMode,
    onParsedCodingChange,
    codebookTree,
    editableCodebookTree,
    selectedFilterCodes,
    postContents,
  });

  const lastVisibleColumnIndex = visibleColumns.length - 1;
  const getVisibleCellStyle = useCallback(
    (columnId, index) => ({
      ...getColumnCellStyle(columnId),
      borderRight: index < lastVisibleColumnIndex ? "1px solid #ffffff" : "none",
    }),
    [getColumnCellStyle, lastVisibleColumnIndex],
  );

  useEffect(() => {
    const syncToParentWidth = () => {
      if (isResizingRef.current) return;
      const wrapperWidth = tableWrapperRef.current?.clientWidth;
      if (!wrapperWidth || visibleColumns.length === 0) return;
      const visibleIds = visibleColumns.map((col) => col.id);
      const fitted = fitVisibleColumnsToWidth(
        visibleIds,
        latestWidthsRef.current,
        wrapperWidth,
      );
      if (!fitted) return;
      const hasMeaningfulDiff = visibleIds.some(
        (id) => Math.abs((latestWidthsRef.current[id] || 0) - fitted[id]) > 0.5,
      );
      if (!hasMeaningfulDiff) return;
      setColumnWidths((prev) => ({ ...prev, ...fitted }));
    };

    syncToParentWidth();
    window.addEventListener("resize", syncToParentWidth);
    return () => window.removeEventListener("resize", syncToParentWidth);
  }, [setColumnWidths, visibleColumns]);

  return (
    <div>
      {saveState?.status === "saving" && (
        <div className="info-message coding-table__status-message">
          Saving coding changes...
        </div>
      )}
      {saveState?.status === "error" && saveState?.message && (
        <div className="error-message coding-table__status-message">
          {saveState.message}
        </div>
      )}
      {saveState?.status === "success" && saveState?.message && (
        <div className="success-message coding-table__status-message">
          {saveState.message}
        </div>
      )}

      {selectedFilterCodes.length > 0 && !isEditMode && (
        <div className="body-sm text-primary coding-table__status-message">
          <strong>Filtering by codes:</strong> {selectedFilterCodes.join(", ")}{" "}
          <button
            onClick={() => setSelectedFilterCodes([])}
            className="btn btn-secondary btn-small"
          >
            Clear Filter
          </button>
        </div>
      )}
      <div className="coding-table-layout">
        <div className="coding-table-layout__legend">
          <CodeLegend
            codebookTree={codebookTree}
            isEditMode={isEditMode}
            draftTree={editableCodebookTree}
            onDraftTreeChange={onEditableCodebookTreeChange}
            disabled={saveState?.status === "saving"}
            onCodingRowCodeRename={onCodingRowCodeRename}
            selectedFilterCodes={selectedFilterCodes}
            onCodeToggle={handleCodeToggle}
            getCodeColor={getCodeColor}
          />
        </div>

        <div className="table-wrapper" ref={tableWrapperRef}>
          <ColumnPicker
            columnVisibility={columnVisibility}
            visibleColumnCount={visibleColumnCount}
            toggleColumnVisibility={toggleColumnVisibility}
          />
          <table className="table table--resizable coding-table">
            <colgroup>
              {visibleColumns.map(({ id }) => (
                <col key={`coding-col-${id}`} style={getColumnCellStyle(id)} />
              ))}
            </colgroup>
            <CodingTableHeader
              visibleColumns={visibleColumns}
              getColumnCellStyle={getColumnCellStyle}
              startColumnResize={startColumnResize}
            />
            <tbody>
              {rowsForRender.map((row) => (
                <React.Fragment key={row.rowKey}>
                  {isEditMode ? (
                    <tr className="table__row--hover">
                      {visibleColumns.map(({ id }, index) => {
                        if (id === "postId") {
                          return (
                            <td key={`${row.rowKey}-postId`} className="table__td" style={getVisibleCellStyle("postId", index)}>
                              <input
                                type="text"
                                className="form__input"
                                value={row.editableItem?.postId || ""}
                                onChange={(e) =>
                                  updateRowPostId(row.sourceIndex, e.target.value)
                                }
                                disabled={saveState?.status === "saving"}
                              />
                            </td>
                          );
                        }
                        if (id === "title") {
                          return (
                            <td key={`${row.rowKey}-title`} className="table__td" style={getVisibleCellStyle("title", index)}>
                              <div className="table__cell-wrap">{row.postTitle}</div>
                            </td>
                          );
                        }
                        if (id === "content") {
                          return (
                            <td
                              key={`${row.rowKey}-content`}
                              className="table__td table__td--content"
                              style={getVisibleCellStyle("content", index)}
                            >
                              <div className="table__cell-wrap">
                                {row.postContent ? (
                                  <div className="table__cell-wrap">
                                    <HighlightedContent
                                      content={row.postContent}
                                      codeEvidence={row.readOnlyCodeEvidence}
                                      getCodeColor={getCodeColor}
                                      onAddCodeFromSelection={(text) =>
                                        appendCodeEvidenceWithText(row.sourceIndex, text)
                                      }
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
                              style={getVisibleCellStyle("codesApplied", index)}
                            >
                              <div className="table__codes-wrap">
                                {row.editCodes.length > 0 ? (
                                  row.editCodes.map((code) => (
                                    <div
                                      key={`${row.rowKey}-edit-code-${code}`}
                                      className="code-badge-container"
                                    >
                                      <div
                                        className="code-badge"
                                        style={{ backgroundColor: getCodeColor(code) }}
                                      >
                                        {code}
                                      </div>
                                    </div>
                                  ))
                                ) : (
                                  <span className="text-muted">No codes configured</span>
                                )}
                              </div>
                            </td>
                          );
                        }
                        return null;
                      })}
                    </tr>
                  ) : (
                    <CodingTableRow
                      row={row}
                      visibleColumns={visibleColumns}
                      getColumnCellStyle={getColumnCellStyle}
                      getCodeColor={getCodeColor}
                    />
                  )}
                  {!isEditMode ? null : (
                    <CodingTableEditRow
                      row={row}
                      columnVisibility={columnVisibility}
                      visibleColumnCount={visibleColumnCount}
                      codeFieldOptions={codeFieldOptions}
                      saveStatus={saveState?.status}
                      updateRowPostId={updateRowPostId}
                      updateRowCodeEvidenceField={updateRowCodeEvidenceField}
                      removeRowCodeEvidence={removeRowCodeEvidence}
                      addRowCodeEvidence={addRowCodeEvidence}
                    />
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default CodingTableView;
