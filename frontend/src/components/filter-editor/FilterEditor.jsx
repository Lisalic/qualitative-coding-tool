import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch, requestJson } from "../../api";
import { useRowMemos } from "../data/useRowMemos";
import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";
import { useToolPanelData } from "../tool-panels/useToolPanelData";
import { useInitialProjectId } from "../tool-panels/useInitialProjectId";
import { MissingFieldsError, buildManualFilterPayload } from "../../lib/apiContracts";
import FilterRowList from "./FilterRowList";
import FilterReaderPane from "./FilterReaderPane";
import FilterDecisionsRail from "./FilterDecisionsRail";
import { useFilterEditorState } from "./useFilterEditorState";
import PageShell from "../shell/PageShell";
import PageEmptyState from "../primitives/PageEmptyState";
import { btn, btnPrimary, input } from "../../lib/uiClasses";

/**
 * Compose a filtered database by hand.
 *
 * 3-pane workspace, matching the coding editor's shape: a compact row
 * list on the left, one row's full text in the center, and the AI
 * assist tool plus the create form on the right. The user reads the
 * source rows and marks each one in or out; nothing is created until
 * Submit.
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
  const { databases, filteredDatabases, projects, error: panelDataError } =
    useToolPanelData();

  const [database, setDatabase] = useState(
    () => location.state?.sourceDatabase || "",
  );
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedProject, setSelectedProject] = useState(initialProjectId);

  const [entries, setEntries] = useState(null);
  const [page, setPage] = useState(0);
  const [limit, setLimit] = useState(25);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [activeKey, setActiveKey] = useState(null);

  const [submitting, setSubmitting] = useState(false);
  const [createdFile, setCreatedFile] = useState(null);

  const editor = useFilterEditorState(database);
  const { getMemo, saveMemo } = useRowMemos(database);

  useEffect(() => {
    setPage(0);
    setCreatedFile(null);
    setActiveKey(null);
  }, [database]);

  const fetchEntries = useCallback(async () => {
    if (!database || !/^proj_[A-Za-z0-9_]+$/.test(String(database))) {
      setEntries(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const response = await apiFetch(
        `/api/file-entries/?limit=${limit}&offset=${page * limit}&schema=${encodeURIComponent(
          String(database),
        )}`,
      );
      if (!response.ok) throw new Error("Failed to load rows");
      setEntries(await response.json());
    } catch (err) {
      setError(err?.message || "Failed to load rows");
      setEntries(null);
    } finally {
      setLoading(false);
    }
  }, [database, limit, page]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  const sourceOptions = useMemo(
    () => [...(databases || []), ...(filteredDatabases || [])],
    [databases, filteredDatabases],
  );

  const rows = useMemo(() => {
    const submissions = (entries?.submissions || []).map((row) => ({ ...row, rowType: "submission" }));
    const comments = (entries?.comments || []).map((row) => ({ ...row, rowType: "comment" }));
    return [...submissions, ...comments];
  }, [entries]);

  const totalRows = (entries?.total_submissions || 0) + (entries?.total_comments || 0);
  const hasNextPage =
    (entries?.total_submissions || 0) > (page + 1) * limit ||
    (entries?.total_comments || 0) > (page + 1) * limit;

  // Default to the first row on the page once it loads, so the reader
  // pane is never empty when there's something to read.
  useEffect(() => {
    if (rows.length === 0) {
      setActiveKey(null);
      return;
    }
    if (!activeKey || !rows.some((r) => `${r.rowType}:${r.id}` === activeKey)) {
      setActiveKey(`${rows[0].rowType}:${rows[0].id}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows]);

  const activeRow = rows.find((r) => `${r.rowType}:${r.id}` === activeKey) || null;

  const handleSubmit = async () => {
    setSubmitting(true);
    setError("");
    setCreatedFile(null);
    try {
      let payload;
      try {
        payload = buildManualFilterPayload({
          database,
          name,
          description,
          projectId: selectedProject || null,
          postIds: editor.included.postIds,
          commentIds: editor.included.commentIds,
        });
      } catch (err) {
        if (err instanceof MissingFieldsError) {
          setError(err.message);
          return;
        }
        throw err;
      }

      const { ok, data, error: submitError } = await requestJson(
        "/api/filtered-data/manual",
        { method: "POST", body: payload },
      );
      if (!ok) {
        setError(submitError || "Failed to create the filtered database");
        return;
      }

      setCreatedFile(data?.file || null);
      // The draft has become an artifact -- starting the next filter of the
      // same source from the set that was just materialized would silently
      // re-add every one of those rows.
      editor.clearDraft();
      setName("");
      setDescription("");
    } catch (err) {
      setError(err?.message || "Failed to create the filtered database");
    } finally {
      setSubmitting(false);
    }
  };

  const { included, excluded } = editor.counts;

  return (
    <PageShell title="Filter Data" width="full" scroll="fill" bodyClassName="gap-3">
      <div className="flex shrink-0 flex-wrap items-end gap-3 border border-line bg-surface p-2.5">
        <div className="flex min-w-[220px] flex-1 flex-col gap-1.5">
          <label htmlFor="filterEditorSource" className="text-sm">
            Source database
          </label>
          <select
            id="filterEditorSource"
            value={database}
            onChange={(e) => setDatabase(e.target.value)}
            className={input}
            disabled={submitting}
          >
            <option value="">Select a database</option>
            {sourceOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
        {database && (
          <div className="text-sm text-paper/60">
            {totalRows} row{totalRows === 1 ? "" : "s"} total
          </div>
        )}
      </div>

      {(error || panelDataError) && (
        <p className="shrink-0 border border-error bg-error/10 px-4 py-2 text-sm text-error">
          {error || panelDataError}
        </p>
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

      {!database ? (
        <PageEmptyState message="Select a database to filter." />
      ) : (
        <>
          <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-hidden lg:grid-cols-[minmax(220px,280px)_minmax(0,1fr)_minmax(260px,320px)] lg:grid-rows-1">
            <FilterRowList
              rows={rows}
              activeKey={activeKey}
              onSelectRow={(row) => setActiveKey(`${row.rowType}:${row.id}`)}
              editor={editor}
              getMemo={getMemo}
              statusFilter={statusFilter}
              onStatusFilterChange={setStatusFilter}
              page={page}
              limit={limit}
              onLimitChange={(next) => {
                setLimit(next);
                setPage(0);
              }}
              hasNextPage={hasNextPage}
              onPrevPage={() => setPage((p) => Math.max(0, p - 1))}
              onNextPage={() => setPage((p) => p + 1)}
              loading={loading}
            />

            <FilterReaderPane
              activeRow={activeRow}
              state={activeRow ? editor.stateOf(activeRow.rowType, activeRow.id) : "undecided"}
              isAiAdded={activeRow ? editor.isAiAdded(activeRow.rowType, activeRow.id) : false}
              onInclude={editor.include}
              onExclude={editor.exclude}
              memo={activeRow ? getMemo(activeRow.rowType, activeRow.id) : null}
              onSaveMemo={saveMemo}
            />

            <FilterDecisionsRail
              database={database}
              decided={editor.decided}
              onAcceptAi={editor.acceptAiSuggestions}
              name={name}
              onNameChange={setName}
              description={description}
              onDescriptionChange={setDescription}
              selectedProject={selectedProject}
              onProjectChange={setSelectedProject}
              projectOptions={projects}
              disabled={submitting}
            />
          </div>

          <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border border-line bg-surface px-4 py-2">
            <div className="text-sm">
              <span className="font-semibold">{included}</span> kept &middot;{" "}
              <span className="font-semibold">{excluded}</span> skipped
              {editor.counts.aiAdded > 0 && (
                <span className="text-paper/60"> &middot; {editor.counts.aiAdded} from AI</span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className={btn}
                onClick={editor.clearDraft}
                disabled={submitting || included + excluded === 0}
              >
                Clear
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={submitting || included === 0 || !name.trim()}
                className={btnPrimary}
              >
                {submitting ? "Creating..." : "Create filtered data"}
              </button>
            </div>
          </div>
        </>
      )}
    </PageShell>
  );
}
