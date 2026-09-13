import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch, requestJson } from "../../api";
import { useRowMemos } from "../data/useRowMemos";
import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";
import PageShell from "../shell/PageShell";
import PageEmptyState from "../primitives/PageEmptyState";
import { useInitialProjectId } from "../tool-panels/useInitialProjectId";
import { useToolPanelData } from "../tool-panels/useToolPanelData";
import {
  MissingFieldsError,
  buildManualCodebookPayload,
} from "../../lib/apiContracts";
import { flattenTreeToCodes, groupCodesByFamily } from "../../lib/codingUtils";
import { btn, btnActive, btnPrimary, select } from "../../lib/uiClasses";
import CodebookCodesRail from "./CodebookCodesRail";
import CodebookReaderPane from "./CodebookReaderPane";
import CodebookSourceReader from "./CodebookSourceReader";
import { useCodebookEditorState } from "./useCodebookEditorState";

const PROJ_SCHEMA_RE = /^proj_[A-Za-z0-9_]+$/;

/**
 * Write a codebook by hand, with the data in front of you.
 *
 * 3-pane workspace, matching the filter and coding editors' shape: a
 * compact row list on the left, one row's full text in the center, and
 * the draft codebook plus the AI assist tool on the right. The AI
 * generator's codes arrive in a review tray (`CodebookProposalTray`)
 * rather than in the codebook directly. Nothing is created or saved
 * until an explicit submit.
 *
 * Two modes, because a codebook is rarely right on the first pass:
 *   New    -- create a fresh codebook (`POST /api/codebook/manual`).
 *   Refine -- open an existing one and do another data-anchored pass over
 *             it (`PUT /api/codebook/{ref}`, the same endpoint the
 *             ViewCodebook editor saves through, so a refinement is an
 *             ordinary new version rather than a special kind of write).
 *
 * The code editor itself is `CodeLegend` -- the same component ViewCodebook
 * and the coding workspace use. There is one code editor in this app, not
 * three, and identity (`code_uid`/`family_uid`) flows through it untouched
 * so a rename stays a rename in the version diff.
 *
 * Drafts live in `localStorage` per (source, target) pair
 * (`useCodebookEditorState`); memos written from a row here go straight to
 * the source database, since the rows on screen ARE source rows.
 */
export default function CodebookEditor() {
  const location = useLocation();
  const initialProjectId = useInitialProjectId();
  const { databases, filteredDatabases, codebooks, projects, error: panelDataError } =
    useToolPanelData({ includeCodebooks: true });

  const [mode, setMode] = useState(() => (location.state?.targetCodebook ? "refine" : "new"));
  const [database, setDatabase] = useState(() => location.state?.sourceDatabase || "");
  const [targetCodebook, setTargetCodebook] = useState(
    () => location.state?.targetCodebook || "",
  );
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedProject, setSelectedProject] = useState(initialProjectId);

  const [entries, setEntries] = useState(null);
  const [page, setPage] = useState(0);
  const [limit, setLimit] = useState(25);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeKey, setActiveKey] = useState(null);

  const [submitting, setSubmitting] = useState(false);
  const [createdFile, setCreatedFile] = useState(null);
  const [savedMessage, setSavedMessage] = useState("");

  const refineRef = mode === "refine" ? targetCodebook : "";
  const editor = useCodebookEditorState(database, refineRef);
  const { getMemo, saveMemo } = useRowMemos(database);
  const { seedDraft } = editor;

  useEffect(() => {
    setPage(0);
    setCreatedFile(null);
    setSavedMessage("");
    setActiveKey(null);
  }, [database]);

  const fetchEntries = useCallback(async () => {
    if (!database || !PROJ_SCHEMA_RE.test(String(database))) {
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

  // Refine mode starts from the chosen codebook's current codes, carrying
  // their real identity so a save reads as the edits actually made rather
  // than a wholesale replacement.
  useEffect(() => {
    if (mode !== "refine" || !targetCodebook) return;
    let cancelled = false;
    (async () => {
      const result = await requestJson(
        `/api/codebook?codebook_id=${encodeURIComponent(targetCodebook)}`,
        { method: "GET" },
      );
      if (cancelled) return;
      if (!result.ok) {
        setError(result.error || "Failed to load the selected codebook");
        return;
      }
      seedDraft(groupCodesByFamily(result.data.codes));
    })();
    return () => {
      cancelled = true;
    };
  }, [mode, targetCodebook, seedDraft]);

  const sourceOptions = useMemo(
    () => [...(databases || []), ...(filteredDatabases || [])],
    [databases, filteredDatabases],
  );
  const codebookOptions = useMemo(
    () =>
      (codebooks || []).filter((entry) => entry?.metadata?.file_type !== "codebook_comparison"),
    [codebooks],
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
    setSavedMessage("");
    const codes = flattenTreeToCodes(editor.draft);
    try {
      if (mode === "refine") {
        if (!targetCodebook) {
          setError("Select a codebook to refine.");
          return;
        }
        if (codes.length === 0) {
          setError("Add at least one code before saving.");
          return;
        }
        const result = await requestJson(
          `/api/codebook/${encodeURIComponent(targetCodebook)}`,
          { method: "PUT", body: { codes } },
        );
        if (!result.ok) {
          setError(result.error || "Failed to save the codebook");
          return;
        }
        setSavedMessage("Saved as a new version.");
        return;
      }

      let payload;
      try {
        payload = buildManualCodebookPayload({
          database,
          name,
          description,
          projectId: selectedProject || null,
          codes,
        });
      } catch (err) {
        if (err instanceof MissingFieldsError) {
          setError(err.message);
          return;
        }
        throw err;
      }

      const { ok, data, error: submitError } = await requestJson("/api/codebook/manual", {
        method: "POST",
        body: payload,
      });
      if (!ok) {
        setError(submitError || "Failed to create the codebook");
        return;
      }

      setCreatedFile(data?.file || null);
      // The draft has become an artifact -- starting the next codebook from
      // the same source would otherwise inherit every code just saved.
      editor.clearDraft();
      setName("");
      setDescription("");
    } catch (err) {
      setError(err?.message || "Failed to save the codebook");
    } finally {
      setSubmitting(false);
    }
  };

  const { draft: draftCount, proposed, aiAccepted } = editor.counts;
  const canSubmit =
    !submitting &&
    draftCount > 0 &&
    Boolean(database) &&
    (mode === "refine" ? Boolean(targetCodebook) : Boolean(name.trim()));

  return (
    <PageShell title="Codebook" width="full" scroll="fill" bodyClassName="gap-3">
      <div className="flex shrink-0 flex-wrap items-end gap-3 border border-line bg-surface p-2.5">
        <div className="flex gap-2" role="group" aria-label="Editor mode">
          <button
            type="button"
            className={`${btn} ${mode === "new" ? btnActive : ""}`}
            aria-pressed={mode === "new"}
            onClick={() => setMode("new")}
            disabled={submitting}
          >
            New
          </button>
          <button
            type="button"
            className={`${btn} ${mode === "refine" ? btnActive : ""}`}
            aria-pressed={mode === "refine"}
            onClick={() => setMode("refine")}
            disabled={submitting}
          >
            Refine existing
          </button>
        </div>

        <div className="flex min-w-[200px] flex-1 flex-col gap-1.5">
          <label htmlFor="codebookEditorSource" className="text-sm">
            Source database
          </label>
          <select
            id="codebookEditorSource"
            value={database}
            onChange={(event) => setDatabase(event.target.value)}
            className={select}
            disabled={submitting}
          >
            <option value="">Select a database</option>
            {sourceOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {mode === "refine" && (
          <div className="flex min-w-[200px] flex-1 flex-col gap-1.5">
            <label htmlFor="codebookEditorTarget" className="text-sm">
              Codebook to refine
            </label>
            <select
              id="codebookEditorTarget"
              value={targetCodebook}
              onChange={(event) => setTargetCodebook(event.target.value)}
              className={select}
              disabled={submitting}
            >
              <option value="">Select a codebook</option>
              {codebookOptions.map((option) => (
                <option key={option.id} value={option.metadata?.schema || option.id}>
                  {option.name}
                </option>
              ))}
            </select>
          </div>
        )}

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

      {savedMessage && (
        <p role="status" className="shrink-0 border border-success bg-success/10 px-4 py-2 text-sm text-success">
          {savedMessage}
        </p>
      )}

      {createdFile && (
        <div className="shrink-0">
          <ArtifactCreatedMessage
            name={createdFile.filename}
            viewPath="/codebook-view"
            viewState={{ selected: createdFile.schema_name }}
          />
        </div>
      )}

      {!database ? (
        <PageEmptyState message="Select a database to build a codebook." />
      ) : (
        <>
          <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-hidden lg:grid-cols-[minmax(220px,280px)_minmax(0,1fr)_minmax(280px,340px)] lg:grid-rows-1">
            <CodebookSourceReader
              rows={rows}
              activeKey={activeKey}
              onSelectRow={(row) => setActiveKey(`${row.rowType}:${row.id}`)}
              loading={loading}
              page={page}
              limit={limit}
              onLimitChange={(next) => {
                setLimit(next);
                setPage(0);
              }}
              hasNextPage={hasNextPage}
              onPrevPage={() => setPage((p) => Math.max(0, p - 1))}
              onNextPage={() => setPage((p) => p + 1)}
              getMemo={getMemo}
            />

            <CodebookReaderPane
              activeRow={activeRow}
              memo={activeRow ? getMemo(activeRow.rowType, activeRow.id) : null}
              onSaveMemo={saveMemo}
            />

            <CodebookCodesRail
              mode={mode}
              name={name}
              onNameChange={setName}
              description={description}
              onDescriptionChange={setDescription}
              selectedProject={selectedProject}
              onProjectChange={setSelectedProject}
              projectOptions={projects}
              editor={editor}
              database={database}
              disabled={submitting}
            />
          </div>

          <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border border-line bg-surface px-4 py-2">
            <span className="text-sm text-paper/70">
              {draftCount} code{draftCount === 1 ? "" : "s"}
              {proposed > 0 ? ` · ${proposed} awaiting review` : ""}
              {aiAccepted > 0 ? ` · ${aiAccepted} from AI` : ""}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                className={btn}
                onClick={editor.clearDraft}
                disabled={submitting || (draftCount === 0 && proposed === 0)}
              >
                Clear
              </button>
              <button
                type="button"
                className={btnPrimary}
                onClick={handleSubmit}
                disabled={!canSubmit}
              >
                {submitting
                  ? "Saving..."
                  : mode === "refine"
                    ? "Save to codebook"
                    : "Create codebook"}
              </button>
            </div>
          </div>
        </>
      )}
    </PageShell>
  );
}
