import React from "react";
import ErrorDisplay from "../components/feedback/ErrorDisplay";
import ExportDropdown from "../components/export/ExportDropdown";
import ArtifactPicker from "../components/primitives/ArtifactPicker";
import MarkdownDisplay from "../components/primitives/MarkdownDisplay";
import PageShell from "../components/shell/PageShell";
import Panel from "../components/shell/Panel";
import PageEmptyState from "../components/primitives/PageEmptyState";
import useViewSummaryPage from "../components/summarize/useViewSummaryPage";

export default function ViewSummary() {
  const {
    available,
    projectsList,
    selectedProject,
    setSelectedProject,
    selected,
    setSelected,
    selectedName,
    content,
    loading,
    error,
  } = useViewSummaryPage();

  return (
    <PageShell
      title={selectedName || "View Summary"}
      width="wide"
      bodyClassName="flex flex-col gap-3"
      actions={
        <div className="flex items-center gap-2">
          <ArtifactPicker
            showProjectFilter={true}
            projects={projectsList || []}
            selectedProject={selectedProject}
            onProjectChange={setSelectedProject}
            items={available}
            selectedId={selected}
            onSelect={setSelected}
            emptyMessage="No summaries available"
            placeholder="Select summary…"
          />
          {selected && (
            <ExportDropdown fileId={selected} artifactType="summary" />
          )}
        </div>
      }
    >
      {loading ? (
        <div className="border border-line bg-surface-raised px-3 py-2 text-sm text-paper/70">
          Loading...
        </div>
      ) : null}

      {error ? <ErrorDisplay error={error} /> : null}

      {!loading && !selected ? (
        <PageEmptyState message="Select a summary to view" />
      ) : null}

      {!loading && selected && content ? (
        <Panel title="Summary Output" scroll="page" bodyClassName="p-4">
          <MarkdownDisplay content={content} />
        </Panel>
      ) : null}
    </PageShell>
  );
}
