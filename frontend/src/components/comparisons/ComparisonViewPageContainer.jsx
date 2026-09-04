import ErrorDisplay from "../feedback/ErrorDisplay";
import ArtifactPicker from "../primitives/ArtifactPicker";
import MarkdownDisplay from "../primitives/MarkdownDisplay";
import PageShell from "../shell/PageShell";
import Panel from "../shell/Panel";
import PageEmptyState from "../primitives/PageEmptyState";
import useViewComparisonPage from "./useViewComparisonPage";

export default function ComparisonViewPageContainer({
  title,
  fileType,
  preselectStateKey,
  contentUrl,
  contentField,
  emptyMessage,
  placeholderMessage,
  pickerPlaceholder,
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
    <PageShell
      title={selectedName || title}
      subtitle={selectedName ? selectedDescription : undefined}
      width="wide"
      bodyClassName="flex flex-col gap-3"
      actions={
        <ArtifactPicker
          showProjectFilter={true}
          projects={projectsList}
          selectedProject={selectedProject}
          onProjectChange={setSelectedProject}
          items={available}
          selectedId={selected}
          onSelect={setSelected}
          emptyMessage={emptyMessage}
          placeholder={pickerPlaceholder}
        />
      }
    >
      {loading ? (
        <div className="border border-line bg-surface-raised px-3 py-2 text-sm text-paper/70">
          Loading...
        </div>
      ) : null}
      <ErrorDisplay message={error} type="error" variant="alert" />

      {content ? (
        <Panel scroll={false}>
          {/* A wide page still needs a readable measure for prose. */}
          <MarkdownDisplay content={content} className="max-w-[75ch] text-paper" />
        </Panel>
      ) : loading || error ? null : (
        <PageEmptyState message={placeholderMessage} />
      )}
    </PageShell>
  );
}
