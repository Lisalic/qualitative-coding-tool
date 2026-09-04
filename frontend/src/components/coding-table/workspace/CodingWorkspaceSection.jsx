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
import PageShell from "../../shell/PageShell";
import { btn, btnSm, btnActive, btnPrimary } from "../../../lib/uiClasses";
import { hasPromptInfo } from "../../../lib/promptInfo";
import { flattenCodebookCodes, getCodeColor } from "../../../lib/codingUtils";

const tabInactive = btn;
const tabActive = `${btn} ${btnActive}`;
const promptBtnClasses = btnSm;

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
 *
 * Layout: this owns its whole route, rendering PageShell with
 * scroll="fill" so the 3-pane grid gets the real remaining viewport height.
 * It previously guessed at that height with `h-[calc(100vh-220px)]` while
 * also setting `min-h-[960px]` -- the floor won on any laptop screen, so
 * the workspace overflowed the very viewport it was sized to fit.
 *
 * `picker` is the artifact selector, rendered into the toolbar rather than
 * as a box above the workspace.
 */
export default function CodingWorkspaceSection({ page, picker = null }) {
  const [showPrompt, setShowPrompt] = useState(false);
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

  if (!selectedCodedData) {
    return (
      <PageShell title="View Coding" actions={picker} width="wide">
        <PageEmptyState message="Select a coding to view" />
      </PageShell>
    );
  }

  const actions = (
    <>
      {picker}
      <ViewModeTabs
        modes={[
          { value: "reader", label: "Reader", activeClassName: tabActive, inactiveClassName: tabInactive },
          { value: "text", label: "Text View", activeClassName: tabActive, inactiveClassName: tabInactive },
        ]}
        activeMode={viewMode}
        onChange={page.setViewMode}
        containerClassName="flex gap-1.5"
      />
      <button
        type="button"
        className={promptBtnClasses}
        onClick={() => navigate(`/versions?ref=${encodeURIComponent(page.selectedCodingSchema)}`)}
      >
        History
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
    </>
  );

  return (
    <PageShell
      title={page.selectedCodedDataName}
      subtitle={page.selectedCodingDescription}
      actions={actions}
      width="full"
      scroll="fill"
      bodyClassName="gap-3"
    >
      {showPrompt && (
        <div className="shrink-0">
          <PromptPanel {...promptInfo} />
        </div>
      )}

      {viewMode === "text" ? (
        <div className="min-h-0 flex-1">
          <CodingTextView schema={page.selectedCodingSchema} refreshKey={page.refreshKey} />
        </div>
      ) : (
        <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-hidden lg:grid-cols-[minmax(220px,280px)_minmax(0,1fr)_minmax(240px,300px)] lg:grid-rows-1">
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
        </div>
      )}

      {/* Pinned by flex rather than `fixed`: the panes above now end exactly
          at the viewport edge, so an overlaying bar would permanently hide
          their last row. */}
      {page.isSessionDirty && (
        <div className="flex shrink-0 flex-wrap items-center justify-center gap-3 border-t-2 border-paper bg-ink px-4 py-2">
          <span className="text-sm">{sessionSummary(page)}</span>
          <button
            type="button"
            className={`${btn} text-paper/70`}
            onClick={page.discardSession}
            disabled={page.sessionSaveState.status === "saving"}
          >
            Discard
          </button>
          <button
            type="button"
            className={`${btnPrimary} bg-paper text-ink hover:bg-ink hover:text-paper`}
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
    </PageShell>
  );
}
