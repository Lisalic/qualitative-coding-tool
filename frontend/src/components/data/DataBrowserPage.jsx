import { useNavigate } from "react-router-dom";
import DataTable from "./DataTable";
import ArtifactPicker from "../primitives/ArtifactPicker";
import PageEmptyState from "../primitives/PageEmptyState";
import ErrorDisplay from "../feedback/ErrorDisplay";
import PageShell from "../shell/PageShell";
import { btn } from "../../lib/uiClasses";

/**
 * Shared frame for the two data browsers (raw and filtered), which differ
 * only in what useDataBrowserPage feeds them.
 *
 * The database picker and the per-database actions live in the toolbar. Both
 * pages previously opened with a `border-2` picker box above a `border ... p-8`
 * table box carrying its own centred `text-3xl` heading -- three frames and
 * two headings before the first row.
 */
export default function DataBrowserPage({ page, pageTitle }) {
  const navigate = useNavigate();

  const {
    projects = [],
    selectedProject,
    setSelectedProject,
    selectedDatabase,
    setSelectedDatabase,
    projectFiles = [],
    fallbackItems = [],
    useProjectFileList,
    selectionProps = {},
    selectedMetadata,
    selectedDescription,
    title,
    displayName,
    tableProps = {},
    listError,
    listLoading,
  } = page;

  const { noProjectFilesMessage, noDatabaseMessage } = selectionProps;
  const { isFilteredView = false, emptyMessage } = tableProps;

  const hasDatabase = Boolean(selectedDatabase && String(selectedDatabase).trim());

  const actions = (
    <>
      <ArtifactPicker
        items={useProjectFileList ? projectFiles : fallbackItems}
        selectedId={selectedDatabase}
        onSelect={setSelectedDatabase}
        showProjectFilter={true}
        projects={projects}
        selectedProject={selectedProject}
        onProjectChange={setSelectedProject}
        emptyMessage={
          useProjectFileList
            ? noProjectFilesMessage || "No files in project"
            : noDatabaseMessage || "No databases available"
        }
        placeholder="Select database…"
        loading={listLoading}
      />
      {hasDatabase ? (
        <>
          <button
            type="button"
            className={btn}
            onClick={() => navigate(`/versions?ref=${encodeURIComponent(selectedDatabase)}`)}
          >
            History
          </button>
          {/* Hand-build a filtered database from this one, with the AI
              filter available as an assistive tool inside the editor. */}
          <button
            type="button"
            className={btn}
            onClick={() =>
              navigate("/filter", {
                state: { sourceDatabase: selectedDatabase, displayName },
              })
            }
          >
            Filter
          </button>
        </>
      ) : null}
    </>
  );

  return (
    <PageShell
      title={hasDatabase ? displayName || title : pageTitle}
      // Once the file's name takes the title, the subtitle keeps saying
      // which browser this is (raw vs filtered).
      subtitle={
        hasDatabase ? [pageTitle, selectedDescription].filter(Boolean).join(" · ") : undefined
      }
      actions={actions}
      width="full"
      bodyClassName="flex flex-col gap-3"
    >
      {hasDatabase ? (
        <DataTable
          database={selectedDatabase}
          isFilteredView={isFilteredView}
          metadata={selectedMetadata}
        />
      ) : listError ? (
        <ErrorDisplay message={listError} variant="alert" />
      ) : (
        <PageEmptyState message={emptyMessage} />
      )}
    </PageShell>
  );
}
