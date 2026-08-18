import CodebookTree from "./CodebookTree";
import ArtifactMarkdownSection from "./ArtifactMarkdownSection";
import ViewModeTabs from "../primitives/ViewModeTabs";
import PageEmptyState from "../primitives/PageEmptyState";

const tabInactive =
  "border border-paper px-4 py-2 text-sm transition-colors hover:bg-paper hover:text-ink";
const tabActive =
  "cursor-default border border-paper bg-paper px-4 py-2 text-sm font-semibold text-ink";

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
    <section className="border-2 border-paper p-6">
      <ViewModeTabs
        modes={[
          {
            value: "markdown",
            label: "Show Text",
            activeClassName: tabActive,
            inactiveClassName: tabInactive,
            disableWhenActive: true,
          },
          {
            value: "tree",
            label: "Show Tree",
            activeClassName: tabActive,
            inactiveClassName: tabInactive,
            disableWhenActive: true,
          },
        ]}
        activeMode={viewMode}
        onChange={onViewModeChange}
        containerClassName="mb-3 flex justify-end gap-2"
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
