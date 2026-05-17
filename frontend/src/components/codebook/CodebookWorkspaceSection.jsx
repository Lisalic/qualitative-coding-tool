import CodebookTree from "./CodebookTree";
import ArtifactMarkdownSection from "./ArtifactMarkdownSection";
import ViewModeTabs from "../primitives/ViewModeTabs";
import PageEmptyState from "../primitives/PageEmptyState";

export default function CodebookWorkspaceSection({
  viewMode,
  onViewModeChange,
  selectedCodebook,
  selectedCodebookName,
  availableCodebooks,
  systemPrompt,
  userPrompt,
  onSelectionChangeAfterSave,
  codebookContent,
  loading,
  error,
}) {
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
            value: "markdown",
            label: "Show Text",
            className: "view-button",
            style: {
              padding: "8px 16px",
              fontSize: "14px",
              cursor: viewMode === "markdown" ? "default" : "pointer",
            },
            disableWhenActive: true,
          },
          {
            value: "tree",
            label: "Show Tree",
            className: "view-button",
            style: {
              padding: "8px 16px",
              fontSize: "14px",
              cursor: viewMode === "tree" ? "default" : "pointer",
            },
            disableWhenActive: true,
          },
        ]}
        activeMode={viewMode}
        onChange={onViewModeChange}
        containerStyle={{
          display: "flex",
          justifyContent: "flex-end",
          gap: 8,
          marginBottom: 12,
        }}
      />

      {viewMode === "markdown" ? (
        <ArtifactMarkdownSection
          artifactType="codebook"
          selectedId={selectedCodebook}
          selectedName={selectedCodebookName}
          availableItems={availableCodebooks}
          systemPrompt={systemPrompt}
          userPrompt={userPrompt}
          onSelectionChangeAfterSave={onSelectionChangeAfterSave}
        />
      ) : null}
      {viewMode === "tree" && selectedCodebook ? (
        <CodebookTree codebookId={selectedCodebook} codebookName={selectedCodebookName} />
      ) : null}
      {!codebookContent && !loading && !error ? (
        <PageEmptyState message="No codebook selected or found. Generate a codebook first." />
      ) : null}
    </section>
  );
}
