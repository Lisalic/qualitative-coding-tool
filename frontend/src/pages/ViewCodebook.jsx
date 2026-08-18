import ArtifactSelector from "../components/primitives/ArtifactSelector";
import CodebookWorkspaceSection from "../components/codebook/CodebookWorkspaceSection";
import useViewCodebookPage from "../components/codebook/useViewCodebookPage";
import ViewPageShell from "../components/shell/ViewPageShell";

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
    <ViewPageShell title="View Codebook">
      <ArtifactSelector
        showProjectFilter={true}
        projects={projectsList || []}
        selectedProject={selectedProject}
        onProjectChange={setSelectedProject}
        items={availableCodebooks}
        selectedId={selectedCodebook}
        onSelect={setSelectedCodebook}
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
    </ViewPageShell>
  );
}
