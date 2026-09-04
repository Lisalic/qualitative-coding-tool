import { useNavigate } from "react-router-dom";
import DataTable from "./DataTable";
import ArtifactPicker from "../primitives/ArtifactPicker";
import PageEmptyState from "../primitives/PageEmptyState";
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
          {/* Hand-build a filtered database from this one, with the AI filter
              available inside the editor as an assistive tool. Distinct from
              `/filter`, which runs the AI filter as the whole operation with
              no review step. */}
          <button
            type="button"
            className={btn}
            onClick={() =>
              navigate("/filter-editor", {
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
      subtitle={hasDatabase ? selectedDescription : undefined}
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
      ) : (
        <PageEmptyState message={emptyMessage} />
      )}
    </PageShell>
  );
}
