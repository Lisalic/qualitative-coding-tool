import { useState } from "react";
import CodingDuplicateControl from "./CodingDuplicateControl";
import CodingTextView from "./CodingTextView";
import CodingDocumentList from "./CodingDocumentList";
import CodingReaderPane from "./CodingReaderPane";
import CodingCodebookSidebar from "./CodingCodebookSidebar";
import ViewModeTabs from "../../primitives/ViewModeTabs";
import PageEmptyState from "../../primitives/PageEmptyState";
import { flattenCodebookCodeNames, getCodeColor } from "../../../lib/codingUtils";

const tabInactive =
  "border border-paper px-3 py-1.5 text-sm transition-colors hover:bg-paper hover:text-ink";
const tabActive = "border border-paper bg-paper px-3 py-1.5 text-sm font-semibold text-ink";
const promptBtnClasses =
  "border border-paper px-2.5 py-1 text-xs transition-colors hover:bg-paper hover:text-ink";

/**
 * 3-pane View Coding workspace, inspired by desktop qualitative coding
 * tools (Taguette/Atlas.ti-style): a compact document list on the left,
 * one document's full text in the center (the only place full post/
 * comment text is ever shown), and the codebook on the right. Select
 * text in the center pane and click a code -- in the popup at the
 * selection, or in the sidebar -- to tag it; no separate "edit mode" or
 * save step for coding itself, each tag auto-saves immediately.
 */
export default function CodingWorkspaceSection({ page }) {
  const [showSystemPrompt, setShowSystemPrompt] = useState(false);
  const [showUserPrompt, setShowUserPrompt] = useState(false);

  const selectedCodedData = page.selectedCodedData;
  const viewMode = page.viewMode;
  const availableCodes = flattenCodebookCodeNames(page.codebookTree);

  if (!selectedCodedData) {
    return (
      <section className="border-2 border-paper p-6">
        <PageEmptyState message="Select a coded data file to view" />
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-3 border-2 border-paper p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold">{page.selectedCodedDataName}</h2>
          {page.selectedCodingDescription && (
            <p className="truncate text-sm text-paper/60">{page.selectedCodingDescription}</p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ViewModeTabs
            modes={[
              { value: "reader", label: "Reader", activeClassName: tabActive, inactiveClassName: tabInactive },
              { value: "text", label: "Text View", activeClassName: tabActive, inactiveClassName: tabInactive },
            ]}
            activeMode={viewMode}
            onChange={page.setViewMode}
            containerClassName="flex gap-1.5"
          />
          {page.systemPrompt && (
            <button
              type="button"
              className={promptBtnClasses}
              onClick={() => setShowSystemPrompt((v) => !v)}
            >
              {showSystemPrompt ? "Hide" : "Show"} System Prompt
            </button>
          )}
          {page.userPrompt && (
            <button
              type="button"
              className={promptBtnClasses}
              onClick={() => setShowUserPrompt((v) => !v)}
            >
              {showUserPrompt ? "Hide" : "Show"} User Prompt
            </button>
          )}
          <CodingDuplicateControl
            defaultName={page.selectedCodedDataName}
            onDuplicate={page.handleDuplicate}
          />
        </div>
      </div>

      {showSystemPrompt && page.systemPrompt && (
        <div className="max-h-[160px] overflow-y-auto whitespace-pre-wrap border border-paper/20 bg-white/5 p-2.5 font-mono text-sm text-paper/80">
          {page.systemPrompt}
        </div>
      )}
      {showUserPrompt && page.userPrompt && (
        <div className="max-h-[160px] overflow-y-auto whitespace-pre-wrap border border-paper/20 bg-white/5 p-2.5 font-mono text-sm text-paper/80">
          {page.userPrompt}
        </div>
      )}

      {viewMode === "text" ? (
        <CodingTextView schema={page.selectedCodingSchema} refreshKey={page.refreshKey} />
      ) : (
        <div className="grid h-[calc(100vh-220px)] min-h-[960px] grid-cols-1 gap-3 overflow-hidden lg:grid-cols-[280px_minmax(0,1fr)_280px] lg:grid-rows-1">
          <CodingDocumentList
            rows={page.rows}
            activeItemId={page.activeItemId}
            onSelectItem={page.setActiveItemId}
            selectedItemIds={page.selectedItemIds}
            onToggleItemSelected={page.toggleItemSelected}
            onlyFilter={page.onlyFilter}
            onOnlyChange={page.setOnlyFilter}
            searchInput={page.searchInput}
            onSearchChange={page.setSearchInput}
            page={page.page}
            pageCount={page.pageCount}
            onPrevPage={page.onPrevPage}
            onNextPage={page.onNextPage}
            activeFilterCode={page.activeFilterCode}
            onClearFilterCode={() => page.toggleFilterCode(page.activeFilterCode)}
            totalRows={page.totalRows}
            totalCoded={page.totalCoded}
            matchingCount={page.rowsTotal}
            disabled={page.rowsLoading}
            onSelectAll={page.selectAllMatching}
            selectAllLoading={page.selectAllLoading}
            recodeProps={{
              selectedCount: page.selectedItemIds.size,
              model: page.recodeModel,
              onModelChange: page.setRecodeModel,
              methodology: page.recodeMethodology,
              onMethodologyChange: page.setRecodeMethodology,
              onRecode: page.handleRecodeSelected,
              onClearSelection: page.clearSelection,
              loading: page.recodeLoading,
              progress: page.recodeProgress,
              error: page.recodeError,
              summary: page.recodeSummary,
            }}
          />

          <CodingReaderPane
            activeRow={page.activeRow}
            availableCodes={availableCodes}
            getCodeColor={getCodeColor}
            pendingSelection={page.pendingSelection}
            onSelectionChange={page.handleSelectionChange}
            onApplyCode={page.applyCodeToSelection}
            onRemoveEntry={page.removeCodeEntry}
            onUpdateNotes={page.updateEntryNotes}
            onRecodeThisDocument={page.recodeThisDocument}
            rowActionError={page.rowActionError}
          />

          <CodingCodebookSidebar
            codebookTree={page.codebookTree}
            getCodeColor={getCodeColor}
            pendingSelection={page.pendingSelection}
            onApplyCode={page.applyCodeToSelection}
            activeFilterCode={page.activeFilterCode}
            onToggleFilterCode={page.toggleFilterCode}
            isEditMode={page.isCodebookEditMode}
            draftTree={page.codebookDraft}
            onDraftTreeChange={page.setCodebookDraft}
            saveState={page.codebookSaveState}
            onBeginEdit={page.beginCodebookEdit}
            onCancelEdit={page.cancelCodebookEdit}
            onSaveEdit={page.saveCodebookEdit}
          />
        </div>
      )}
    </section>
  );
}
