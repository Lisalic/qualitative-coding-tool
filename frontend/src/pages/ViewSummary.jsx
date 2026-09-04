import React from "react";
import ErrorDisplay from "../components/feedback/ErrorDisplay";
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
        <PageEmptyState message="Select a summary to view" />
      )}
    </PageShell>
  );
}
