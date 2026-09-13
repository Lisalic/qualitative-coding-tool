import { useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { requestJson } from "../../api";
import { useRowMemos } from "../data/useRowMemos";
import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";
import ErrorDisplay from "../feedback/ErrorDisplay";
import { useToolPanelData } from "../tool-panels/useToolPanelData";
import { useInitialProjectId } from "../tool-panels/useInitialProjectId";
import { MissingFieldsError, buildManualFilterPayload } from "../../lib/apiContracts";
import FilterRowList from "./FilterRowList";
import FilterReaderPane from "./FilterReaderPane";
import FilterDecisionsRail from "./FilterDecisionsRail";
import { useFilterEditorState } from "./useFilterEditorState";
import { useEditorRows, rowKey } from "../editor-shell/useEditorRows";
import { useEditorShortcuts } from "../editor-shell/useEditorShortcuts";
import EditorSetupStep from "../editor-shell/EditorSetupStep";
import EditorOutputFields from "../editor-shell/EditorOutputFields";
import EditorWorkspace from "../editor-shell/EditorWorkspace";
import EditorActionBar from "../editor-shell/EditorActionBar";
import PageShell from "../shell/PageShell";
import Dropdown from "../primitives/Dropdown";
import { btn, select } from "../../lib/uiClasses";

/**
 * Compose a filtered database by hand.
 *
 * Two steps, matching the codebook and coding editors: a setup step
 * picks the source database and names the artifact this session will
 * become, then the workspace opens -- a compact row list on the left,
 * one row's full text in the center, and the AI assist tool on the
 * right. The user reads the source rows and marks each one in or out;
 * nothing is created until Submit.
 *
 * Selections live in `localStorage` per source database
 * (`useFilterEditorState`); memos are saved straight to the source
 * database as they are written, because the rows on screen ARE source
 * rows -- they are then copied into the new artifact along with their
 * rows on submit (`data_service._materialize_filtered_schema`).
 */
export default function FilterEditor() {
  const location = useLocation();
  const initialProjectId = useInitialProjectId();
  const { databases, filteredDatabases, projects, loading: panelDataLoading, error: panelDataError } =
    useToolPanelData();

  const [started, setStarted] = useState(false);
  const [database, setDatabase] = useState(() => location.state?.sourceDatabase || "");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedProject, setSelectedProject] = useState(initialProjectId);
  const [statusFilter, setStatusFilter] = useState("all");

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [createdFile, setCreatedFile] = useState(null);

  const editor = useFilterEditorState(database);
  const { getMemo, saveMemo } = useRowMemos(database);
  const {
    rows,
    totalRows,
    hasNextPage,
    loading,
    loadError,
    page,
    setPage,
    limit,
    setLimit,
    activeKey,
    setActiveKey,
    activeRow,
  } = useEditorRows(database);

  const sourceOptions = useMemo(
    () => [...(databases || []), ...(filteredDatabases || [])],
    [databases, filteredDatabases],
  );

  useEditorShortcuts(
    {
      j: () => stepRow(1),
      k: () => stepRow(-1),
    },
    { enabled: started },
  );
  function stepRow(delta) {
    if (rows.length === 0) return;
    const currentIndex = rows.findIndex((r) => rowKey(r) === activeKey);
    const nextIndex = currentIndex === -1 ? 0 : Math.min(rows.length - 1, Math.max(0, currentIndex + delta));
    if (rows[nextIndex]) setActiveKey(rowKey(rows[nextIndex]));
  }

  const handleSubmit = async () => {
    setSubmitting(true);
    setSubmitError("");
    setCreatedFile(null);
    try {
      let payload;
      try {
        payload = buildManualFilterPayload({
          database,
          name,
          description,
          projectId: selectedProject,
          postIds: editor.included.postIds,
          commentIds: editor.included.commentIds,
          assistRuns: editor.assistRuns,
        });
      } catch (err) {
        if (err instanceof MissingFieldsError) {
          setSubmitError(err.message);
          return;
        }
        throw err;
      }

      const { ok, data, error: postError } = await requestJson("/api/filtered-data/manual", {
        method: "POST",
        body: payload,
      });
      if (!ok) {
        setSubmitError(postError || "Failed to create the filtered database");
        return;
      }

      setCreatedFile(data?.file || null);
      // The draft has become an artifact -- starting the next filter of the
      // same source from the set that was just materialized would silently
      // re-add every one of those rows.
      editor.clearDraft();
    } catch (err) {
      setSubmitError(err?.message || "Failed to create the filtered database");
    } finally {
      setSubmitting(false);
    }
  };

  const { included, excluded } = editor.counts;

  if (!started) {
    return (
      <PageShell title="Filter Data" width="wide">
        <EditorSetupStep
          sourceTitle="Source data"
          sourceFields={
            <div className="flex flex-col gap-1.5">
              <label htmlFor="filterEditorSource" className="text-sm">
                Source database
              </label>
              <Dropdown
                id="filterEditorSource"
                value={database}
                options={sourceOptions}
                onChange={setDatabase}
                placeholder="Select a database"
                loadingLabel={panelDataLoading ? "Loading..." : undefined}
                triggerClassName={`w-full ${select}`}
                listLabel="Source database"
                searchPlaceholder="Search databases…"
                emptyMessage="No databases match that search."
              />
            </div>
          }
          outputFields={
            <EditorOutputFields
              idPrefix="filterEditor"
              name={name}
              onNameChange={setName}
              namePlaceholder="my-filtered-db"
              nameLabel="Filtered database name"
              description={description}
              onDescriptionChange={setDescription}
              selectedProject={selectedProject}
              onProjectChange={setSelectedProject}
              projectOptions={projects}
            />
          }
          onSubmit={() => setStarted(true)}
          submitLabel="Continue"
          submitLoadingLabel="Continue"
          submitDisabled={!database || !name.trim() || !selectedProject}
          error={panelDataError}
        />
      </PageShell>
    );
  }

  return (
    <EditorWorkspace
      title="Filter Data"
      subtitle={`${totalRows} row${totalRows === 1 ? "" : "s"} total`}
      actions={
        <button type="button" className={btn} onClick={() => setStarted(false)}>
          Change source
        </button>
      }
      banners={
        <>
          {loadError && (
            <div className="shrink-0">
              <ErrorDisplay message={loadError} variant="alert" />
            </div>
          )}
          {createdFile && (
            <div className="shrink-0">
              <ArtifactCreatedMessage
                name={createdFile.filename}
                viewPath="/filtered-data"
                viewState={{ selectedDatabase: createdFile.schema_name }}
                neutral
              />
            </div>
          )}
        </>
      }
      list={
        <FilterRowList
          rows={rows}
          activeKey={activeKey}
          onSelectRow={(row) => setActiveKey(rowKey(row))}
          editor={editor}
          getMemo={getMemo}
          statusFilter={statusFilter}
          onStatusFilterChange={setStatusFilter}
          page={page}
          limit={limit}
          onLimitChange={setLimit}
          hasNextPage={hasNextPage}
          onPrevPage={() => setPage((p) => Math.max(0, p - 1))}
          onNextPage={() => setPage((p) => p + 1)}
          loading={loading}
        />
      }
      reader={
        <FilterReaderPane
          activeRow={activeRow}
          state={activeRow ? editor.stateOf(activeRow.rowType, activeRow.id) : "undecided"}
          isAiDecided={activeRow ? editor.isAiDecided(activeRow.rowType, activeRow.id) : false}
          onInclude={editor.include}
          onExclude={editor.exclude}
          memo={activeRow ? getMemo(activeRow.rowType, activeRow.id) : null}
          onSaveMemo={saveMemo}
        />
      }
      rail={
        <FilterDecisionsRail
          database={database}
          included={editor.included}
          excluded={editor.excluded}
          onAcceptAi={editor.acceptAiSuggestions}
          disabled={submitting}
        />
      }
      actionBar={
        <EditorActionBar
          summary={
            <>
              <span className="font-semibold">{included}</span> kept &middot;{" "}
              <span className="font-semibold">{excluded}</span> skipped
              {editor.counts.aiDecided > 0 && (
                <span className="text-paper/60"> &middot; {editor.counts.aiDecided} from AI</span>
              )}
            </>
          }
          secondaryLabel="Clear"
          onSecondary={editor.clearDraft}
          secondaryDisabled={submitting || included + excluded === 0}
          primaryLabel="Save"
          primaryLoadingLabel="Saving..."
          primaryLoading={submitting}
          onPrimary={handleSubmit}
          primaryDisabled={submitting || included === 0}
          errorMessage={submitError}
        />
      }
    />
  );
}
