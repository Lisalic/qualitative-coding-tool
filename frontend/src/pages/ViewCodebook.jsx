import ArtifactPicker from "../components/primitives/ArtifactPicker";
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
    codebookTree,
    selectedCodebookName,
    loading,
    error,
    listError,
    listLoading,
    systemPrompt,
    instructions,
    promptMeta,
    isEditMode,
    codebookDraft,
    setCodebookDraft,
    saveState,
    beginEdit,
    cancelEdit,
    saveEdit,
  } = useViewCodebookPage();

  return (
    <CodebookWorkspaceSection
      picker={
        <ArtifactPicker
          showProjectFilter={true}
          projects={projectsList || []}
          selectedProject={selectedProject}
          onProjectChange={setSelectedProject}
          items={availableCodebooks}
          selectedId={selectedCodebook}
          onSelect={setSelectedCodebook}
          emptyMessage="No codebooks available"
          loading={listLoading}
          placeholder="Select codebook…"
        />
      }
      selectedCodebook={selectedCodebook}
      selectedCodebookName={selectedCodebookName}
      systemPrompt={systemPrompt}
      instructions={instructions}
      promptMeta={promptMeta}
      codebookTree={codebookTree}
      loading={loading}
      error={error}
      listError={listError}
      isEditMode={isEditMode}
      codebookDraft={codebookDraft}
      setCodebookDraft={setCodebookDraft}
      saveState={saveState}
      onBeginEdit={beginEdit}
      onCancelEdit={cancelEdit}
      onSaveEdit={saveEdit}
    />
  );
}
