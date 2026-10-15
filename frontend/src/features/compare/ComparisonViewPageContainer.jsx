import ErrorDisplay from "../../components/feedback/ErrorDisplay";
import ExportDropdown from "../export/ExportDropdown";
import ArtifactPicker from "../../components/primitives/ArtifactPicker";
import MarkdownDisplay from "../../components/primitives/MarkdownDisplay";
import PageShell from "../../components/layout/PageShell";
import Panel from "../../components/layout/Panel";
import PageEmptyState from "../../components/primitives/PageEmptyState";
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
    listError,
    listLoading,
  } = useViewComparisonPage({ fileType, preselectStateKey, contentUrl, contentField });

  return (
    <PageShell
      title={selectedName || title}
      subtitle={selectedName ? selectedDescription : undefined}
      width="wide"
      bodyClassName="flex flex-col gap-3"
      actions={
        <div className="flex items-center gap-2">
          <ArtifactPicker
            showProjectFilter={true}
            projects={projectsList}
            selectedProject={selectedProject}
            onProjectChange={setSelectedProject}
            items={available}
            selectedId={selected}
            onSelect={setSelected}
            emptyMessage={emptyMessage}
            loading={listLoading}
            placeholder={pickerPlaceholder}
          />
          {selected && <ExportDropdown fileId={selected} artifactType="document" />}
        </div>
      }
    >
      {loading ? (
        <div className="border border-line bg-surface-raised px-3 py-2 text-sm text-paper/70">
          Loading…
        </div>
      ) : null}
      <ErrorDisplay message={error || (!selected ? listError : null)} type="error" variant="alert" />

      {content ? (
        <Panel scroll={false}>
          {/* MarkdownDisplay keeps the prose measure per block, so tables
              can use the page's full width. */}
          <MarkdownDisplay content={content} className="text-paper" />
        </Panel>
      ) : loading || error || (!selected && listError) ? null : (
        <PageEmptyState message={placeholderMessage} />
      )}
    </PageShell>
  );
}
