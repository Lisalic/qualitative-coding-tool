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

const tdClasses = "border-b border-r border-paper/20 px-3 py-2.5 last:border-r-0";
const inputClasses =
  "border border-paper bg-white/5 px-3 py-2 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";

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
        <div className="mb-2.5 border border-paper/20 bg-white/5 px-4 py-3 text-sm text-paper/70">
          Saving coding changes...
        </div>
      )}
      {saveState?.status === "error" && saveState?.message && (
        <div className="mb-2.5 border border-error bg-error/10 px-4 py-3 text-sm text-error">
          {saveState.message}
        </div>
      )}
      {saveState?.status === "success" && saveState?.message && (
        <div className="mb-2.5 border border-success bg-success/10 px-4 py-3 text-sm text-success">
          {saveState.message}
        </div>
      )}

      {selectedFilterCodes.length > 0 && !isEditMode && (
        <div className="mb-2.5 text-sm">
          <strong>Filtering by codes:</strong> {selectedFilterCodes.join(", ")}{" "}
          <button
            type="button"
            onClick={() => setSelectedFilterCodes([])}
            className="border border-paper px-2.5 py-1 text-xs transition-colors hover:bg-paper hover:text-ink"
          >
            Clear Filter
          </button>
        </div>
      )}
      <div className="grid grid-cols-[minmax(260px,320px)_minmax(0,1fr)] items-start gap-4">
        <div className="sticky top-20 z-[2] max-h-[calc(100vh-96px)] self-start overflow-y-auto">
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

        <div className="overflow-x-auto border border-paper" ref={tableWrapperRef}>
          <ColumnPicker
            columnVisibility={columnVisibility}
            visibleColumnCount={visibleColumnCount}
            toggleColumnVisibility={toggleColumnVisibility}
          />
          <table className="w-full table-fixed border-collapse">
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
                    <tr className="transition-colors hover:bg-white/5">
                      {visibleColumns.map(({ id }) => {
                        if (id === "postId") {
                          return (
                            <td key={`${row.rowKey}-postId`} className={tdClasses} style={getColumnCellStyle("postId")}>
                              <input
                                type="text"
                                className={inputClasses}
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
                            <td key={`${row.rowKey}-title`} className={tdClasses} style={getColumnCellStyle("title")}>
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
                              className={`${tdClasses} min-w-0 overflow-hidden`}
                              style={getColumnCellStyle("codesApplied")}
                            >
                              <div className="flex min-w-0 flex-wrap gap-1 overflow-hidden">
                                {row.editCodes.length > 0 ? (
                                  row.editCodes.map((code) => (
                                    <div
                                      key={`${row.rowKey}-edit-code-${code}`}
                                      className="m-0.5 inline-flex min-w-0 max-w-full items-center"
                                    >
                                      <div
                                        className="inline-block max-w-full truncate px-2 py-1 text-sm font-bold text-ink"
                                        style={{ backgroundColor: getCodeColor(code) }}
                                      >
                                        {code}
                                      </div>
                                    </div>
                                  ))
                                ) : (
                                  <span className="text-paper/60">No codes configured</span>
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
