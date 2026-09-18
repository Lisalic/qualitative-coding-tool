import ArtifactPicker from "../components/primitives/ArtifactPicker";
import PageShell from "../components/shell/PageShell";
import PageEmptyState from "../components/primitives/PageEmptyState";
import VersionHistoryPanel from "../components/versioning/VersionHistoryPanel";
import useVersionHistoryPage from "../components/versioning/useVersionHistoryPage";

/**
 * The standalone Version History page (`/versions?ref=...`) -- every
 * "History" button in the app (codebook workspace, coding workspace,
 * data pages, project file rows) redirects here with the artifact
 * preselected, rather than opening an inline sidebar panel. See
 * `useVersionHistoryPage`'s docstring for why the ref lives in the URL.
 */
export default function VersionHistory() {
  const {
    ref,
    navigateTo,
    history,
    available,
    projectsList,
    selectedProject,
    setSelectedProject,
    selectedArtifact,
    duplicateFrom,
  } = useVersionHistoryPage();

  return (
    <PageShell
      title={selectedArtifact?.display_name || "Version History"}
      subtitle={selectedArtifact?.description}
      width="full"
      actions={
        <ArtifactPicker
          showProjectFilter={true}
          projects={projectsList}
          selectedProject={selectedProject}
          onProjectChange={setSelectedProject}
          items={available}
          selectedId={ref}
          onSelect={navigateTo}
          emptyMessage="No files available"
          placeholder="Select file…"
        />
      }
    >
      {!ref ? (
        <PageEmptyState message="Select a file to view its version history" />
      ) : (
        <VersionHistoryPanel
          history={history}
          fileType={selectedArtifact?.file_type}
          onDuplicateFrom={duplicateFrom}
        />
      )}
    </PageShell>
  );
}
