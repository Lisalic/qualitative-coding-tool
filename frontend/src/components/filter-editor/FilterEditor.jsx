import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch, requestJson } from "../../api";
import EntryModal from "../data/EntryModal";
import { useRowMemos } from "../data/useRowMemos";
import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";
import { useToolPanelData } from "../tool-panels/useToolPanelData";
import { useInitialProjectId } from "../tool-panels/useInitialProjectId";
import { MissingFieldsError, buildManualFilterPayload } from "../../lib/apiContracts";
import FilterAiPanel from "./FilterAiPanel";
import FilterEditorTable from "./FilterEditorTable";
import { useFilterEditorState } from "./useFilterEditorState";
import PageShell from "../shell/PageShell";
import { btnPrimary } from "../../lib/uiClasses";

const inputClasses =
  "border border-paper bg-white/5 px-3 py-2.5 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";
const btnClasses =
  "border border-paper px-3 py-1.5 text-sm transition-colors hover:bg-paper hover:text-ink disabled:opacity-40";

const PAGE_SIZES = [10, 25, 50, 100, 200];

const SUBMISSION_COLUMNS = [
  { key: "title", label: "Title", truncate: true },
  { key: "selftext", label: "Selftext", truncate: true },
  { key: "author", label: "Author" },
];
const COMMENT_COLUMNS = [
  { key: "body", label: "Body", truncate: true },
  { key: "author", label: "Author" },
];

function StepHeading({ number, title, description, aside }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-paper/30 pb-4">
      <div className="flex items-start gap-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center border-2 border-paper text-sm font-bold">
          {number}
        </span>
        <div>
          <h2 className="font-semibold">{title}</h2>
          {description && <p className="mt-0.5 text-sm text-paper/60">{description}</p>}
        </div>
      </div>
      {aside}
    </div>
  );
}

function DecisionSummary({ included, excluded, total }) {
  const reviewed = Math.min(total, included + excluded);
  const undecided = Math.max(0, total - reviewed);
  const progress = total > 0 ? Math.round((reviewed / total) * 100) : 0;
  return (
    <div className="grid min-w-[280px] grid-cols-3 border border-paper/30 text-center">
      <div className="border-r border-paper/30 px-3 py-2">
        <strong className="block text-lg">{included}</strong>
        <span className="text-[11px] uppercase tracking-wide text-paper/50">Keep</span>
      </div>
      <div className="border-r border-paper/30 px-3 py-2">
        <strong className="block text-lg">{excluded}</strong>
        <span className="text-[11px] uppercase tracking-wide text-paper/50">Skip</span>
      </div>
      <div className="px-3 py-2">
        <strong className="block text-lg">{undecided}</strong>
        <span className="text-[11px] uppercase tracking-wide text-paper/50">Undecided</span>
      </div>
      <div className="col-span-3 h-1 bg-white/10" aria-label={`${progress}% reviewed`}>
        <div className="h-full bg-paper transition-[width]" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}

/**
 * Compose a filtered database by hand.
 *
 * The human-in-the-loop counterpart of `/filter`: instead of writing a
 * prompt and receiving a finished artifact, the user reads the source rows
 * and marks each one in or out, with the AI filter available inside the
 * screen as an assistant whose picks arrive as reviewable suggestions
 * (`FilterAiPanel`). Nothing is created until Submit.
 *
 * Selections live in `localStorage` per source database
 * (`useFilterEditorState`); memos are saved straight to the source
 * database as they are written, because the rows on screen ARE source
 * rows -- they are then copied into the new artifact along with their rows
 * on submit (`data_service._materialize_filtered_schema`).
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

  const [selectedEntry, setSelectedEntry] = useState(null);
  const [showModal, setShowModal] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [createdFile, setCreatedFile] = useState(null);

  const editor = useFilterEditorState(database);
  const { getMemo, saveMemo } = useRowMemos(database);

  useEffect(() => {
    setPage(0);
    setCreatedFile(null);
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

  const submissions = entries?.submissions || [];
  const comments = entries?.comments || [];
  const totalRows = (entries?.total_submissions || 0) + (entries?.total_comments || 0);
  const hasNextPage =
    (entries?.total_submissions || 0) > (page + 1) * limit ||
    (entries?.total_comments || 0) > (page + 1) * limit;

  const openRow = (row, rowType) => {
    setSelectedEntry({ ...row, type: rowType });
    setShowModal(true);
  };

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
  const reviewed = Math.min(totalRows, included + excluded);

  return (
    <PageShell title="Filter Editor" width="full" bodyClassName="flex flex-col gap-3">
      <section className="flex flex-col gap-3 border border-line bg-surface p-3">
        <StepHeading
          number="1"
          title="Select source data"
        />

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="filterEditorSource" className="text-sm">
            Source database
          </label>
          <select
            id="filterEditorSource"
            value={database}
            onChange={(e) => setDatabase(e.target.value)}
            className={inputClasses}
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

        <div className="flex flex-col gap-1.5">
          <label htmlFor="filterEditorName" className="text-sm">
            Filtered database name
          </label>
          <input
            id="filterEditorName"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="my-filtered-db"
            className={inputClasses}
            disabled={submitting}
          />
        </div>

        <div className="flex flex-col gap-1.5 md:col-span-2">
          <label htmlFor="filterEditorDescription" className="text-sm">
            Description (optional)
          </label>
          <textarea
            id="filterEditorDescription"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description for the filtered database"
            rows={2}
            className={`${inputClasses} resize-y`}
            disabled={submitting}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="filterEditorProject" className="text-sm">
            Project (optional)
          </label>
          <select
            id="filterEditorProject"
            value={selectedProject || ""}
            onChange={(e) => setSelectedProject(e.target.value)}
            className={inputClasses}
            disabled={submitting}
          >
            <option value="">No project</option>
            {(projects || []).map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.projectname}
              </option>
            ))}
          </select>
        </div>
        </div>
      </section>

      {(error || panelDataError) && (
        <p className="border border-paper/40 bg-white/5 px-4 py-3 text-sm text-paper">
          {error || panelDataError}
        </p>
      )}

      {createdFile && (
        <ArtifactCreatedMessage
          name={createdFile.filename}
          viewPath="/filtered-data"
          viewState={{ selectedDatabase: createdFile.schema_name }}
          neutral
        />
      )}

      {!database ? (
        <section className="border border-line bg-surface px-5 py-8 text-center">
          <div className="mx-auto mb-3 flex h-8 w-8 items-center justify-center border border-paper/40 text-paper/60">2</div>
          <h2 className="font-semibold">Review source data</h2>
          <p className="mt-1 text-sm text-paper/60">Select a source database above to begin.</p>
        </section>
      ) : (
        <>
          <section className="border border-line bg-surface p-3">
            <StepHeading
              number="2"
              title="Review source data"
              aside={<DecisionSummary included={included} excluded={excluded} total={totalRows} />}
            />

            <div className="my-3 flex flex-wrap items-center justify-between gap-3 border-b border-line-soft pb-3">
              <div className="text-sm text-paper/70">
                {reviewed} of {totalRows} row{totalRows === 1 ? "" : "s"} reviewed
              </div>
              <div className="flex items-center gap-2 text-sm">
                <label htmlFor="filterEditorLimit">Rows per page</label>
                <select
                  id="filterEditorLimit"
                  value={limit}
                  onChange={(e) => {
                    setLimit(Number(e.target.value));
                    setPage(0);
                  }}
                  className="border border-paper bg-white/5 px-2 py-1 text-paper"
                >
                  {PAGE_SIZES.map((size) => (
                    <option key={size} value={size}>
                      {size}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {loading && (
              <p className="mb-4 border border-paper/20 bg-white/5 px-4 py-3 text-sm text-paper/70">
                Loading rows...
              </p>
            )}

            <FilterEditorTable
              rowType="submission"
              rows={submissions}
              columns={SUBMISSION_COLUMNS}
              editor={editor}
              getMemo={getMemo}
              onSaveMemo={saveMemo}
              onOpenRow={openRow}
            />
            <FilterEditorTable
              rowType="comment"
              rows={comments}
              columns={COMMENT_COLUMNS}
              editor={editor}
              getMemo={getMemo}
              onSaveMemo={saveMemo}
              onOpenRow={openRow}
            />

            {!loading && submissions.length === 0 && comments.length === 0 && (
              <p className="border border-paper/20 bg-white/5 px-4 py-3 text-sm text-paper/70">
                No rows on this page.
              </p>
            )}

            <div className="mt-4 flex items-center justify-center gap-2">
              <button
                type="button"
                className={btnClasses}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
              >
                Previous
              </button>
              <span className="text-sm">Page {page + 1}</span>
              <button
                type="button"
                className={btnClasses}
                onClick={() => setPage((p) => p + 1)}
                disabled={!hasNextPage}
              >
                Next
              </button>
            </div>
          </section>

          {/* Below the table, not above it: hand-marking rows is the primary
              loop, and the assistant is something the coder reaches for once
              they have worked through what is on screen. */}
          <FilterAiPanel
            database={database}
            decided={editor.decided}
            onAccept={editor.acceptAiSuggestions}
            disabled={submitting}
          />

          <div className="sticky bottom-0 z-20 flex flex-wrap items-center justify-between gap-3 border-2 border-paper bg-ink px-4 py-2">
            <div>
              <div className="text-sm">
              <span className="font-semibold">{included}</span> kept ·{" "}
              <span className="font-semibold">{excluded}</span> skipped
              {editor.counts.aiAdded > 0 && (
                <span className="text-paper/60"> · {editor.counts.aiAdded} from AI</span>
              )}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className={btnClasses}
                onClick={editor.clearDraft}
                disabled={submitting || included + excluded === 0}
              >
                Clear decisions
              </button>
              <button
                type="button"
                onClick={handleSubmit}
                disabled={submitting || included === 0 || !name.trim()}
                className={btnPrimary}
              >
                {submitting ? "Creating..." : "Create filtered database"}
              </button>
            </div>
          </div>
        </>
      )}

      <EntryModal
        entry={selectedEntry}
        isOpen={showModal}
        onClose={() => {
          setShowModal(false);
          setSelectedEntry(null);
        }}
        database={database}
        memo={selectedEntry ? getMemo(selectedEntry.type, selectedEntry.id) : null}
        onSaveMemo={saveMemo}
      />
    </PageShell>
  );
}
