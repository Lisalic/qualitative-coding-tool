import CodingEditActionsBar from "./CodingEditActionsBar";
import CodingSavePanel from "./CodingSavePanel";
import CodingTableView from "../../coding-table/CodingTableView";
import ArtifactMarkdownSection from "../../codebook/ArtifactMarkdownSection";
import ViewModeTabs from "../../primitives/ViewModeTabs";
import PageEmptyState from "../../primitives/PageEmptyState";
import { getCodeColor } from "../../../lib/codingUtils";

export default function CodingWorkspaceSection({ page }) {
  const selectedCodedData = page.selectedCodedData;
  const viewMode = page.viewMode;

  return (
    <section
      style={{
        border: "1px solid #ffffff",
        borderRadius: "8px",
        padding: "20px",
        backgroundColor: "#000000",
      }}
    >
      <ViewModeTabs
        modes={[
          {
            value: "text",
            label: "Text View",
            activeClassName: "project-tab",
            inactiveClassName: "db-button",
            style: { padding: "8px 16px" },
          },
          {
            value: "table",
            label: "Table View",
            activeClassName: "project-tab",
            inactiveClassName: "db-button",
            style: { padding: "8px 16px" },
          },
        ]}
        activeMode={viewMode}
        onChange={page.setViewMode}
        disabled={!selectedCodedData}
        containerStyle={{ marginBottom: "16px", display: "flex", gap: "8px" }}
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
        <PageEmptyState
          style={{ color: "#888", padding: 20 }}
          message="Select a coded data file to view"
        />
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
