import { useState } from "react";
import { useNavigate } from "react-router-dom";
import CodingDuplicateControl from "./CodingDuplicateControl";
import CodingTextView from "./CodingTextView";
import CodingDocumentList from "./CodingDocumentList";
import CodingReaderPane from "./CodingReaderPane";
import CodingCodebookSidebar from "./CodingCodebookSidebar";
import ViewModeTabs from "../../primitives/ViewModeTabs";
import PageEmptyState from "../../primitives/PageEmptyState";
import PromptPanel from "../../primitives/PromptPanel";
import { hasPromptInfo } from "../../../lib/promptInfo";
import VersionHistoryPanel from "../../versioning/VersionHistoryPanel";
import useVersionHistory from "../../versioning/useVersionHistory";
import { flattenCodebookCodes, getCodeColor } from "../../../lib/codingUtils";

const tabInactive =
  "border border-paper px-3 py-1.5 text-sm transition-colors hover:bg-paper hover:text-ink";
const tabActive = "border border-paper bg-paper px-3 py-1.5 text-sm font-semibold text-ink";
const promptBtnClasses =
  "border border-paper px-2.5 py-1 text-xs transition-colors hover:bg-paper hover:text-ink";

/** One-line summary of everything staged in the current editing session
 * -- rows changed (broken out by how many came from an accepted AI
 * recode proposal) and whether the codebook itself was edited -- shown
 * in the bottom Save/Discard bar (see useViewCodingPage's docstring for
 * what "session" means here).
 */
function sessionSummary(page) {
  const parts = [];
  if (page.pendingRowEditCount > 0) {
    const aiCount = page.aiProposedPendingCount || 0;
    const rowsLabel = `${page.pendingRowEditCount} row${page.pendingRowEditCount === 1 ? "" : "s"} changed`;
    parts.push(aiCount > 0 ? `${rowsLabel} (${aiCount} by AI)` : rowsLabel);
  }
  if (page.isCodebookDirty) parts.push("codebook edited");
  return parts.join(" \u00b7 ") || "Unsaved changes";
}

/**
 * 3-pane View Coding workspace, inspired by desktop qualitative coding
 * tools (Taguette/Atlas.ti-style): a compact document list on the left,
 * one document's full text in the center (the only place full post/
 * comment text is ever shown), and the codebook on the right. Select
 * text in the center pane and click a code -- in the popup at the
 * selection, or in the sidebar -- to tag it. Manual tagging, codebook
 * edits, and accepted AI recode proposals all accumulate in ONE editing
 * session (see useViewCodingPage's docstring); the bottom bar appears
 * the moment any of them is dirty, and Save Changes flushes the whole
 * session in a single request.
 */
export default function CodingWorkspaceSection({ page }) {
  const [showPrompt, setShowPrompt] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const navigate = useNavigate();

  const promptInfo = {
    systemPrompt: page.systemPrompt,
    instructions: page.instructions,
    promptMeta: page.promptMeta,
  };

  const selectedCodedData = page.selectedCodedData;
  const viewMode = page.viewMode;
  // Read from the DRAFT, not the last-saved codebookTree -- a code
  // created this session (client-minted uid, see CodeLegend's addCode)
  // must be immediately taggable, not just after a Save.
  const availableCodes = flattenCodebookCodes(page.codebookDraft);

  const history = useVersionHistory(page.selectedCodingSchema);
  const handleDuplicateFrom = async (versionNo, displayName) => {
    const result = await page.handleDuplicate(displayName, versionNo);
    return result;
  };

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
          <button type="button" className={promptBtnClasses} onClick={() => setShowHistory((v) => !v)}>
            {showHistory ? "Hide" : "Show"} History
          </button>
          <button
            type="button"
            className={promptBtnClasses}
            onClick={() => navigate("/lineage", { state: { ref: page.selectedCodingSchema } })}
          >
            Lineage
          </button>
          {hasPromptInfo(promptInfo) && (
            <button type="button" className={promptBtnClasses} onClick={() => setShowPrompt((v) => !v)}>
              {showPrompt ? "Hide" : "Show"} Prompt
            </button>
          )}
          <CodingDuplicateControl
            defaultName={page.selectedCodedDataName}
            onDuplicate={page.handleDuplicate}
          />
        </div>
      </div>

      {showPrompt && <PromptPanel {...promptInfo} />}

      {viewMode === "text" ? (
        <CodingTextView schema={page.selectedCodingSchema} refreshKey={page.refreshKey} />
      ) : (
        <div
          className={`grid h-[calc(100vh-220px)] min-h-[960px] grid-cols-1 gap-3 overflow-hidden lg:grid-rows-1 ${
            showHistory
              ? "lg:grid-cols-[280px_minmax(0,1fr)_280px_280px]"
              : "lg:grid-cols-[280px_minmax(0,1fr)_280px]"
          }`}
        >
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
            isAiProposed={page.activeRow ? page.aiProposedItemIds.has(page.activeRow.item_id) : false}
          />

          <CodingCodebookSidebar
            codebookTree={page.codebookDraft}
            getCodeColor={getCodeColor}
            pendingSelection={page.pendingSelection}
            onApplyCode={page.applyCodeToSelection}
            activeFilterCode={page.activeFilterCode}
            onToggleFilterCode={page.toggleFilterCode}
            isEditMode={page.isCodebookEditMode}
            isDirty={page.isCodebookDirty}
            draftTree={page.codebookDraft}
            onDraftTreeChange={page.setCodebookDraft}
            onBeginEdit={page.beginCodebookEdit}
            onFinishEdit={page.finishCodebookEdit}
            onCancelEdit={page.cancelCodebookEdit}
          />

          {showHistory && (
            <VersionHistoryPanel
              history={history}
              onClose={() => setShowHistory(false)}
              onDuplicateFrom={handleDuplicateFrom}
            />
          )}
        </div>
      )}

      {page.isSessionDirty && (
        <div className="fixed inset-x-0 bottom-0 z-50 flex flex-wrap items-center justify-center gap-3 border-t-2 border-paper bg-ink px-4 py-3 shadow-[0_-2px_12px_rgba(0,0,0,0.3)]">
          <span className="text-sm">{sessionSummary(page)}</span>
          <button
            type="button"
            className="border border-paper px-3 py-1.5 text-sm text-paper/70 transition-colors hover:bg-paper hover:text-ink"
            onClick={page.discardSession}
            disabled={page.sessionSaveState.status === "saving"}
          >
            Discard
          </button>
          <button
            type="button"
            className="border-2 border-paper bg-paper px-4 py-1.5 text-sm font-semibold text-ink transition-colors hover:bg-ink hover:text-paper disabled:opacity-40"
            onClick={page.saveSession}
            disabled={page.sessionSaveState.status === "saving"}
          >
            {page.sessionSaveState.status === "saving" ? "Saving..." : "Save Changes"}
          </button>
          {page.sessionSaveState.status === "error" && (
            <span className="text-sm text-error">{page.sessionSaveState.message}</span>
          )}
        </div>
      )}
    </section>
  );
}
