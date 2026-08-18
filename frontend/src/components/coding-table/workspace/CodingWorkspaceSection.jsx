import CodingEditActionsBar from "./CodingEditActionsBar";
import CodingSavePanel from "./CodingSavePanel";
import CodingTableView from "../../coding-table/CodingTableView";
import ArtifactMarkdownSection from "../../codebook/ArtifactMarkdownSection";
import ViewModeTabs from "../../primitives/ViewModeTabs";
import PageEmptyState from "../../primitives/PageEmptyState";
import { getCodeColor } from "../../../lib/codingUtils";

const tabInactive =
  "border border-paper px-4 py-2 text-sm transition-colors hover:bg-paper hover:text-ink";
const tabActive =
  "border border-paper bg-paper px-4 py-2 text-sm font-semibold text-ink";

export default function CodingWorkspaceSection({ page }) {
  const selectedCodedData = page.selectedCodedData;
  const viewMode = page.viewMode;

  return (
    <section className="border-2 border-paper p-6">
      <ViewModeTabs
        modes={[
          {
            value: "text",
            label: "Text View",
            activeClassName: tabActive,
            inactiveClassName: tabInactive,
          },
          {
            value: "table",
            label: "Table View",
            activeClassName: tabActive,
            inactiveClassName: tabInactive,
          },
        ]}
        activeMode={viewMode}
        onChange={page.setViewMode}
        disabled={!selectedCodedData}
        containerClassName="mb-4 flex gap-2"
      />
      <CodingEditActionsBar
        selectedCodedData={selectedCodedData}
        viewMode={viewMode}
        isTableEditMode={page.isTableEditMode}
        onBeginEdit={page.beginTableEditMode}
        onCancelEdit={page.cancelTableEditMode}
        saveStatus={page.tableSaveState.status}
      />
      {!selectedCodedData ? (
        <PageEmptyState message="Select a coded data file to view" />
      ) : null}
      {selectedCodedData && viewMode === "text" ? (
        <ArtifactMarkdownSection
          artifactType="coding"
          selectedId={selectedCodedData}
          selectedName={page.selectedCodedDataName}
          description={page.selectedCodingDescription}
          selectedSchema={page.selectedCodingSchema}
          refreshKey={page.refreshKey}
          systemPrompt={page.systemPrompt}
          userPrompt={page.userPrompt}
          onSaved={page.handleMarkdownSaved}
        />
      ) : null}
      {selectedCodedData && viewMode === "table" ? (
        <>
          <CodingTableView
            parsedCoding={page.parsedCoding}
            editableParsedCoding={page.tableDraftParsedCoding}
            isEditMode={page.isTableEditMode}
            onParsedCodingChange={page.setTableDraftParsedCoding}
            codebookTree={page.codebookTree}
            editableCodebookTree={page.tableDraftCodebookTree}
            onEditableCodebookTreeChange={page.setTableDraftCodebookTree}
            onCodingRowCodeRename={page.propagateCodingRowCodeRename}
            postContents={page.postContents}
            selectedFilterCodes={page.selectedFilterCodes}
            setSelectedFilterCodes={page.setSelectedFilterCodes}
            getCodeColor={getCodeColor}
            saveState={page.tableSaveState}
          />
          <CodingSavePanel
            isTableEditMode={page.isTableEditMode}
            tableEditName={page.tableEditName}
            onTableEditNameChange={page.setTableEditName}
            onSaveDuplicate={page.handleTableSaveDuplicate}
            onSaveOverwrite={page.handleTableSaveOverwrite}
            saveStatus={page.tableSaveState.status}
          />
        </>
      ) : null}
    </section>
  );
}
