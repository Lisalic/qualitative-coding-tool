import { useState } from "react";
import { useNavigate } from "react-router-dom";
import ExportDropdown from "../../export/ExportDropdown";
import CodingDuplicateControl from "./CodingDuplicateControl";
import CodingTextView from "./CodingTextView";
import CodingQuoteBank from "./CodingQuoteBank";
import CodingDocumentList from "./CodingDocumentList";
import CodingReaderPane from "./CodingReaderPane";
import CodingCodebookSidebar from "./CodingCodebookSidebar";
import CodingAiPanel from "./CodingAiPanel";
import ViewModeTabs from "../../primitives/ViewModeTabs";
import PageEmptyState from "../../primitives/PageEmptyState";
import PromptPanel from "../../primitives/PromptPanel";
import PageShell from "../../shell/PageShell";
import EditorRail from "../../editor-shell/EditorRail";
import EditorActionBar from "../../editor-shell/EditorActionBar";
import { EDITOR_GRID_CLASSES } from "../../editor-shell/EditorWorkspace";
import { useEditorShortcuts } from "../../editor-shell/useEditorShortcuts";
import { btn, btnSm, btnActive } from "../../../lib/uiClasses";
import { hasPromptInfo } from "../../../lib/promptInfo";
import { flattenCodebookCodes, getCodeColor } from "../../../lib/codingUtils";

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
  return parts.join(" · ") || "Unsaved changes";
}

/**
 * 3-pane View Coding workspace, inspired by desktop qualitative coding
 * tools (Taguette/Atlas.ti-style): a compact document list on the left,
 * one document's full text in the center (the only place full post/
 * comment text is ever shown), and a tabbed rail on the right --
 * Codebook, AI Coding, Coverage. Select text in the center pane and click a code -- in
 * the popup at the selection, or in the sidebar -- to tag it. Manual
 * tagging, codebook edits, and accepted AI recode proposals all
 * accumulate in ONE editing session (see useViewCodingPage's docstring);
 * the bottom bar appears the moment any of them is dirty, and Save
 * Changes flushes the whole session in a single request.
 *
 * Layout: this owns its whole route, rendering PageShell with
 * scroll="fill" so the 3-pane grid gets the real remaining viewport
 * height, and shares its grid column widths (`EDITOR_GRID_CLASSES`) with
 * the filter and codebook editors' workspace step -- it can't use
 * `EditorWorkspace` outright because of the Text View branch below,
 * which isn't a 3-pane layout at all.
 *
 * `leadingActions` opens the toolbar: the artifact selector on View
 * Coding, a back-to-setup button on Apply Codebook, which renders this
 * same workspace on the artifact it just created. `emptyTitle`/
 * `emptyMessage` cover the no-artifact-selected state, which only View
 * Coding can actually reach (Apply Codebook renders its setup step
 * instead of this component until an artifact exists).
 */
export default function CodingWorkspaceSection({
  page,
  leadingActions = null,
  emptyTitle = "View Coding",
  emptyMessage = "Select a coding to view",
}) {
  const [showPrompt, setShowPrompt] = useState(false);
  const [railTab, setRailTab] = useState("codebook");
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

  // j/k step through the document list without leaving the keyboard,
  // mirroring the reader pane's 1-9 code shortcuts. Reader mode only --
  // Text View has no per-document list to step through. Built on
  // `useEditorShortcuts` so this subscribes once rather than on every
  // render: `page` is a fresh object literal each render, which used to
  // tear down and re-add this `document` listener continuously.
  useEditorShortcuts(
    {
      j: () => stepActiveItem(1),
      k: () => stepActiveItem(-1),
    },
    { enabled: viewMode === "reader" },
  );

  function stepActiveItem(delta) {
    const rows = page.rows || [];
    if (rows.length === 0) return;
    const currentIndex = rows.findIndex((row) => row.item_id === page.activeItemId);
    const nextIndex = currentIndex === -1 ? 0 : Math.min(rows.length - 1, Math.max(0, currentIndex + delta));
    if (rows[nextIndex]) page.setActiveItemId(rows[nextIndex].item_id);
  }

  if (!selectedCodedData) {
    return (
      <PageShell title={emptyTitle} actions={leadingActions} width="wide">
        <PageEmptyState message={emptyMessage} />
      </PageShell>
    );
  }

  const actions = (
    <>
      {leadingActions}
      <ViewModeTabs
        modes={[
          { value: "reader", label: "Reader", activeClassName: `${btn} ${btnActive}`, inactiveClassName: btn },
          { value: "text", label: "Text View", activeClassName: `${btn} ${btnActive}`, inactiveClassName: btn },
          { value: "quotes", label: "Quote Bank", activeClassName: `${btn} ${btnActive}`, inactiveClassName: btn },
        ]}
        activeMode={viewMode}
        onChange={page.setViewMode}
        containerClassName="flex gap-1.5"
      />
      <button
        type="button"
        className={btnSm}
        onClick={() => navigate(`/versions?ref=${encodeURIComponent(page.selectedCodingSchema)}`)}
      >
        History
      </button>
      <button
        type="button"
        className={btnSm}
        onClick={() => navigate("/lineage", { state: { ref: page.selectedCodingSchema } })}
      >
        Lineage
      </button>
      {hasPromptInfo(promptInfo) && (
        <button type="button" className={btnSm} onClick={() => setShowPrompt((v) => !v)}>
          {showPrompt ? "Hide" : "Show"} Prompt
        </button>
      )}
      <ExportDropdown fileId={page.selectedCodingSchema} artifactType="coding" />
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
      ) : viewMode === "quotes" ? (
        <div className="min-h-0 flex-1">
          <CodingQuoteBank
            schema={page.selectedCodingSchema}
            availableCodes={availableCodes}
            refreshKey={page.refreshKey}
          />
        </div>
      ) : (
        <div className={EDITOR_GRID_CLASSES}>
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
            loading={page.rowsLoading}
            onSelectAll={page.selectAllMatching}
            onSelectUncoded={page.selectUncodedMatching}
            selectAllLoading={page.selectAllLoading}
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
            onRecodeThisDocument={() => {
              page.recodeThisDocument();
              setRailTab("ai");
            }}
          />

          <EditorRail scroll={false}>
            <CodingCodebookSidebar
              activeTab={railTab}
              onTabChange={setRailTab}
              selectedCount={page.selectedItemIds.size}
              aiPanel={
                <CodingAiPanel
                  selectedCount={page.selectedItemIds.size}
                  matchingCount={page.rowsTotal}
                  hasActiveDocument={Boolean(page.activeItemId)}
                  onSelectAll={page.selectAllMatching}
                  onSelectUncoded={page.selectUncodedMatching}
                  onSelectThisDocument={page.recodeThisDocument}
                  onClearSelection={page.clearSelection}
                  selectAllLoading={page.selectAllLoading}
                  model={page.recodeModel}
                  onModelChange={page.setRecodeModel}
                  methodology={page.recodeMethodology}
                  onMethodologyChange={page.setRecodeMethodology}
                  onRecode={page.handleRecodeSelected}
                  loading={page.recodeLoading}
                  progress={page.recodeProgress}
                  error={page.recodeError}
                  summary={page.recodeSummary}
                />
              }
              schema={page.selectedCodingSchema}
              refreshKey={page.refreshKey}
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
          </EditorRail>
        </div>
      )}

      {/* Pinned by flex rather than `fixed`: the panes above now end exactly
          at the viewport edge, so an overlaying bar would permanently hide
          their last row. */}
      {page.isSessionDirty && (
        <EditorActionBar
          emphasized
          summary={sessionSummary(page)}
          secondaryLabel="Discard"
          onSecondary={page.discardSession}
          secondaryDisabled={page.sessionSaveState.status === "saving"}
          primaryLabel="Save"
          primaryLoadingLabel="Saving..."
          primaryLoading={page.sessionSaveState.status === "saving"}
          onPrimary={page.saveSession}
          primaryDisabled={page.sessionSaveState.status === "saving"}
          errorMessage={page.sessionSaveState.status === "error" ? page.sessionSaveState.message : null}
        />
      )}
    </PageShell>
  );
}
