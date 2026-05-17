import "../styles/Data.css";
import "../styles/DataTable.css";
import ArtifactSelector from "../components/primitives/ArtifactSelector";
import CodebookWorkspaceSection from "../components/codebook/CodebookWorkspaceSection";
import useViewCodebookPage from "../components/codebook/useViewCodebookPage";

export default function ViewCodebook() {
  const {
    availableCodebooks,
    selectedCodebook,
    setSelectedCodebook,
    projectsList,
    selectedProject,
    setSelectedProject,
    codebookContent,
    selectedCodebookName,
    loading,
    error,
    viewMode,
    setViewMode,
    systemPrompt,
    userPrompt,
    handleSelectionChangeAfterSave,
  } = useViewCodebookPage();

  return (
    <div className="data-container">
      <ArtifactSelector
        showProjectFilter={true}
        projects={projectsList || []}
        selectedProject={selectedProject}
        onProjectChange={setSelectedProject}
        filterStyle={{ marginBottom: 12 }}
        items={availableCodebooks}
        selectedId={selectedCodebook}
        onSelect={setSelectedCodebook}
        listClassName="codebook-selector"
        buttonClassName="db-button"
        emptyMessage="No codebooks available"
      />
      <CodebookWorkspaceSection
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        selectedCodebook={selectedCodebook}
        selectedCodebookName={selectedCodebookName}
        availableCodebooks={availableCodebooks}
        systemPrompt={systemPrompt}
        userPrompt={userPrompt}
        onSelectionChangeAfterSave={handleSelectionChangeAfterSave}
        codebookContent={codebookContent}
        loading={loading}
        error={error}
      />
    </div>
  );
}
