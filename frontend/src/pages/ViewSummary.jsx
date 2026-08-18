import React from "react";
import ErrorDisplay from "../components/feedback/ErrorDisplay";
import ArtifactSelector from "../components/primitives/ArtifactSelector";
import MarkdownDisplay from "../components/primitives/MarkdownDisplay";
import ViewPageShell from "../components/shell/ViewPageShell";
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
    <ViewPageShell title="View Summary">
      <ArtifactSelector
        showProjectFilter={true}
        projects={projectsList || []}
        selectedProject={selectedProject}
        onProjectChange={setSelectedProject}
        items={available}
        selectedId={selected}
        onSelect={setSelected}
        emptyMessage="No summaries available"
      />

      {loading ? (
        <div className="border border-paper/20 bg-white/5 px-4 py-3 text-sm text-paper/70">
          Loading...
        </div>
      ) : null}
      <ErrorDisplay message={error} type="error" variant="alert" />

      {content ? (
        <div className="border-2 border-paper p-6">
          <h2 className="mb-3 text-lg font-semibold">{selectedName || "Summary"}</h2>
          <MarkdownDisplay content={content} className="text-paper" />
        </div>
      ) : null}
    </ViewPageShell>
  );
}
