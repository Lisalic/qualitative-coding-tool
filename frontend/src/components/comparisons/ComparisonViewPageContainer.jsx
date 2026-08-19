import ErrorDisplay from "../feedback/ErrorDisplay";
import ArtifactSelector from "../primitives/ArtifactSelector";
import MarkdownDisplay from "../primitives/MarkdownDisplay";
import ViewPageShell from "../shell/ViewPageShell";
import useViewComparisonPage from "./useViewComparisonPage";

export default function ComparisonViewPageContainer({
  title,
  fileType,
  preselectStateKey,
  contentUrl,
  contentField,
  emptyMessage,
}) {
  const {
    available,
    projectsList,
    selectedProject,
    setSelectedProject,
    selected,
    setSelected,
    selectedName,
    selectedDescription,
    content,
    loading,
    error,
  } = useViewComparisonPage({ fileType, preselectStateKey, contentUrl, contentField });

  return (
    <ViewPageShell title={title}>
      <ArtifactSelector
        showProjectFilter={true}
        projects={projectsList}
        selectedProject={selectedProject}
        onProjectChange={setSelectedProject}
        items={available}
        selectedId={selected}
        onSelect={setSelected}
        emptyMessage={emptyMessage}
      />

      {loading ? (
        <div className="border border-paper/20 bg-white/5 px-4 py-3 text-sm text-paper/70">
          Loading...
        </div>
      ) : null}
      <ErrorDisplay message={error} type="error" variant="alert" />

      {content ? (
        <div className="border-2 border-paper p-6">
          <h2 className="mb-1 text-lg font-semibold">{selectedName || "Comparison"}</h2>
          {selectedDescription ? (
            <p className="mb-3 text-sm text-paper/70">{selectedDescription}</p>
          ) : null}
          <MarkdownDisplay content={content} className="text-paper" />
        </div>
      ) : null}
    </ViewPageShell>
  );
}
