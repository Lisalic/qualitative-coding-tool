import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { requestJson } from "../../api";
import { useRowMemos } from "../data/useRowMemos";
import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";
import ErrorDisplay from "../feedback/ErrorDisplay";
import PageShell from "../shell/PageShell";
import { useInitialProjectId } from "../tool-panels/useInitialProjectId";
import { useToolPanelData } from "../tool-panels/useToolPanelData";
import {
  MissingFieldsError,
  buildManualCodebookPayload,
} from "../../lib/apiContracts";
import { draftStorageKey } from "../../lib/codebookEditorState";
import { flattenTreeToCodes, groupCodesByFamily } from "../../lib/codingUtils";
import Dropdown from "../primitives/Dropdown";
import { btn, btnActive, select } from "../../lib/uiClasses";
import { useEditorRows, rowKey } from "../editor-shell/useEditorRows";
import { useEditorShortcuts } from "../editor-shell/useEditorShortcuts";
import EditorSetupStep from "../editor-shell/EditorSetupStep";
import EditorOutputFields from "../editor-shell/EditorOutputFields";
import EditorWorkspace from "../editor-shell/EditorWorkspace";
import EditorActionBar from "../editor-shell/EditorActionBar";
import CodebookBuilderPane from "./CodebookBuilderPane";
import CodebookReferenceRail from "./CodebookReferenceRail";
import CodebookSourceReader from "./CodebookSourceReader";
import { useCodebookEditorState } from "./useCodebookEditorState";

/**
 * Write a codebook by hand, with the data in front of you.
 *
 * Two steps, matching the filter and coding editors: setup picks the
 * source database (and, in Refine mode, the codebook to refine) and
 * names the output, then the workspace opens. Unlike Filter and Apply
 * Codebook, what's being built isn't decided per row -- it's the code
 * tree itself, so the workspace runs `EditorWorkspace` with
 * `emphasis="builder"`: source rows on the left, the draft codebook
 * (`CodebookBuilderPane`) as the wide center pane, and the active row's
 * text plus the AI generator in a reference rail on the right. The AI
 * generator's codes arrive in a review tray above the draft, not
 * directly in it. Nothing is created or saved until an explicit submit.
 *
 * Two modes: **New** creates a fresh codebook (`POST /api/codebook/manual`).
 * **Refine** opens an existing one for another data-anchored pass
 * (`PUT /api/codebook/{ref}`, the same endpoint ViewCodebook saves
 * through) and asks only for the codebook -- its source database comes
 * from its own lineage, with `Use another database` to override.
 *
 * The code editor itself is `CodeLegend`, the same component ViewCodebook
 * and the coding workspace use -- one code editor in this app, not three.
 * Drafts live in `localStorage` per (source, target) pair
 * (`useCodebookEditorState`); memos written from a row go straight to the
 * source database, since the rows on screen ARE source rows.
 */
export default function CodebookEditor() {
  const location = useLocation();
  const initialProjectId = useInitialProjectId();
  const { databases, filteredDatabases, codebooks, projects, loading: panelDataLoading, error: panelDataError } =
    useToolPanelData({ includeCodebooks: true });

  const [started, setStarted] = useState(false);
  const [mode, setMode] = useState(() => (location.state?.targetCodebook ? "refine" : "new"));
  const [database, setDatabase] = useState(() => location.state?.sourceDatabase || "");
  const [targetCodebook, setTargetCodebook] = useState(
    () => location.state?.targetCodebook || "",
  );
  const [sourceOverride, setSourceOverride] = useState(false);
  const [autoSource, setAutoSource] = useState({ loading: false, error: "" });
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedProject, setSelectedProject] = useState(initialProjectId);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [createdFile, setCreatedFile] = useState(null);
  const [savedMessage, setSavedMessage] = useState("");

  const refineRef = mode === "refine" ? targetCodebook : "";
  // Empty string (not draftStorageKey("", "")) when no source is picked
  // yet, matching the hook's own "falsy key -> emptyState, no storage
  // access" contract.
  const editor = useCodebookEditorState(database ? draftStorageKey(database, refineRef) : "");
  const { getMemo, saveMemo } = useRowMemos(database);
  const { seedDraft } = editor;
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

  useEffect(() => {
    setSavedMessage("");
    setSourceOverride(false);
    setAutoSource({ loading: false, error: "" });
  }, [mode, targetCodebook]);

  // Refine mode starts from the chosen codebook's current codes, carrying
  // their real identity so a save reads as the edits actually made rather
  // than a wholesale replacement. Seeded only into an EMPTY draft --
  // re-running this on every render (or every remount, e.g. navigating
  // away and back) used to overwrite whatever unsaved refine edits
  // `useCodebookEditorState` had just restored from localStorage. Once a
  // draft has content (from a prior seed, or from the researcher's own
  // edits), `editor.draft.length > 0` holds permanently and the effect
  // no-ops for good -- `seededRef` only guards the narrower window while
  // a fetch is still in flight (including React StrictMode's dev-only
  // double-invoke: marking `seededRef` INSIDE the async callback, after
  // confirming the effect wasn't cleaned up, means the deliberately-
  // cancelled first invocation never marks it, so the second, real
  // invocation still fires its own fetch instead of finding a
  // pre-marked key and skipping silently).
  const seededRef = useRef(new Set());
  useEffect(() => {
    if (mode !== "refine" || !targetCodebook) return undefined;
    if (editor.draft.length > 0 || editor.counts.proposed > 0) return undefined;
    const key = `${database}::${targetCodebook}`;
    if (seededRef.current.has(key)) return undefined;

    let cancelled = false;
    (async () => {
      const result = await requestJson(
        `/api/codebook?codebook_id=${encodeURIComponent(targetCodebook)}`,
        { method: "GET" },
      );
      if (cancelled) return;
      if (!result.ok) {
        setSubmitError(result.error || "Failed to load the selected codebook");
        return;
      }
      seededRef.current.add(key);
      seedDraft(groupCodesByFamily(result.data.codes));
    })();
    return () => {
      cancelled = true;
    };
  }, [mode, targetCodebook, database, seedDraft, editor.draft, editor.counts.proposed]);

  // Refine mode reads the source database off the codebook's own lineage
  // rather than asking again: the codebook was written against a specific
  // database, and re-reading those same rows is the point of a second
  // pass. `Use another database` (below) drops back to the picker for the
  // rarer case of refining against fresh data.
  useEffect(() => {
    if (mode !== "refine" || !targetCodebook || sourceOverride) return undefined;

    let cancelled = false;
    setAutoSource({ loading: true, error: "" });
    (async () => {
      const result = await requestJson(
        `/api/artifacts/${encodeURIComponent(targetCodebook)}/lineage`,
        { method: "GET" },
      );
      if (cancelled) return;
      if (!result.ok) {
        setAutoSource({
          loading: false,
          error: result.error || "Failed to load the codebook's source database",
        });
        return;
      }
      const parent = (result.data?.parents || []).find(
        (entry) => entry.file_type === "raw_data" || entry.file_type === "filtered_data",
      );
      if (!parent?.schema_name) {
        setAutoSource({
          loading: false,
          error: "This codebook has no recorded source database -- pick one.",
        });
        setSourceOverride(true);
        return;
      }
      setDatabase(parent.schema_name);
      setAutoSource({ loading: false, error: "" });
    })();
    return () => {
      cancelled = true;
    };
  }, [mode, targetCodebook, sourceOverride]);

  const sourceOptions = useMemo(
    () => [...(databases || []), ...(filteredDatabases || [])],
    [databases, filteredDatabases],
  );
  const codebookOptions = useMemo(
    () =>
      (codebooks || []).filter((entry) => entry?.metadata?.file_type !== "codebook_comparison"),
    [codebooks],
  );
  const codebookChoices = useMemo(
    () =>
      codebookOptions.map((option) => ({
        value: option.metadata?.schema || option.id,
        label: option.name,
      })),
    [codebookOptions],
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
    setSavedMessage("");
    const codes = flattenTreeToCodes(editor.draft);
    try {
      if (mode === "refine") {
        if (!targetCodebook) {
          setSubmitError("Select a codebook to refine.");
          return;
        }
        if (codes.length === 0) {
          setSubmitError("Add at least one code before saving.");
          return;
        }
        const result = await requestJson(
          `/api/codebook/${encodeURIComponent(targetCodebook)}`,
          { method: "PUT", body: { codes, assist_runs: editor.assistRuns } },
        );
        if (!result.ok) {
          setSubmitError(result.error || "Failed to save the codebook");
          return;
        }
        setSavedMessage("Saved as a new version.");
        // Deliberately NOT cleared: the draft now equals what the server
        // just committed, and refine is continuous editing of ONE
        // artifact -- unlike "new" mode below, there is no next artifact
        // for a blank draft to prepare for.
        return;
      }

      let payload;
      try {
        payload = buildManualCodebookPayload({
          database,
          name,
          description,
          projectId: selectedProject,
          codes,
          assistRuns: editor.assistRuns,
        });
      } catch (err) {
        if (err instanceof MissingFieldsError) {
          setSubmitError(err.message);
          return;
        }
        throw err;
      }

      const { ok, data, error: postError } = await requestJson("/api/codebook/manual", {
        method: "POST",
        body: payload,
      });
      if (!ok) {
        setSubmitError(postError || "Failed to create the codebook");
        return;
      }

      setCreatedFile(data?.file || null);
      // The draft has become an artifact -- starting the next codebook from
      // the same source would otherwise inherit every code just saved.
      editor.clearDraft();
    } catch (err) {
      setSubmitError(err?.message || "Failed to save the codebook");
    } finally {
      setSubmitting(false);
    }
  };

  const { draft: draftCount, proposed, aiAccepted } = editor.counts;
  const outputReady =
    mode === "refine"
      ? Boolean(targetCodebook)
      : Boolean(name.trim()) && Boolean(selectedProject);
  const canSubmit = !submitting && draftCount > 0 && Boolean(database) && outputReady;
  const canContinue = Boolean(database) && outputReady;

  const showSourcePicker = mode !== "refine" || sourceOverride;
  const sourceLabel =
    sourceOptions.find((option) => option.value === database)?.label || database;

  if (!started) {
    return (
      <PageShell title="Create Codebook" width="wide">
        <EditorSetupStep
          sourceTitle="Source data"
          sourceFields={
            <>
              <div className="flex flex-col gap-1.5">
                <label className="text-sm">Mode</label>
                <div className="flex gap-2" role="group" aria-label="Editor mode">
                  <button
                    type="button"
                    className={`flex-1 ${btn} ${mode === "new" ? btnActive : ""}`}
                    aria-pressed={mode === "new"}
                    onClick={() => setMode("new")}
                  >
                    New
                  </button>
                  <button
                    type="button"
                    className={`flex-1 ${btn} ${mode === "refine" ? btnActive : ""}`}
                    aria-pressed={mode === "refine"}
                    onClick={() => setMode("refine")}
                  >
                    Refine existing
                  </button>
                </div>
              </div>

              {mode === "refine" && (
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="codebookEditorTarget" className="text-sm">
                    Codebook to refine
                  </label>
                  <Dropdown
                    id="codebookEditorTarget"
                    value={targetCodebook}
                    options={codebookChoices}
                    onChange={setTargetCodebook}
                    placeholder="Select a codebook"
                    triggerClassName={`w-full ${select}`}
                    listLabel="Codebook to refine"
                    searchPlaceholder="Search codebooks…"
                    emptyMessage="No codebooks match that search."
                  />
                </div>
              )}

              {showSourcePicker ? (
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="codebookEditorSource" className="text-sm">
                    Source database
                  </label>
                  <Dropdown
                    id="codebookEditorSource"
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
                  {autoSource.error && (
                    <p className="text-sm text-error">{autoSource.error}</p>
                  )}
                </div>
              ) : (
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm">Source database</label>
                  <p className="text-sm text-paper/60">
                    {!targetCodebook
                      ? "Select a codebook -- its own source database is used."
                      : autoSource.loading
                        ? "Finding the codebook's source database..."
                        : autoSource.error || sourceLabel || "Not recorded"}
                  </p>
                  <div>
                    <button
                      type="button"
                      className={btn}
                      onClick={() => setSourceOverride(true)}
                    >
                      Use another database
                    </button>
                  </div>
                </div>
              )}
            </>
          }
          outputTitle="Output"
          outputFields={
            mode === "refine" ? null : (
              <EditorOutputFields
                idPrefix="codebookEditor"
                name={name}
                onNameChange={setName}
                namePlaceholder="my-codebook"
                nameLabel="Codebook name"
                description={description}
                onDescriptionChange={setDescription}
                selectedProject={selectedProject}
                onProjectChange={setSelectedProject}
                projectOptions={projects}
              />
            )
          }
          onSubmit={() => setStarted(true)}
          submitLabel="Continue"
          submitLoadingLabel="Continue"
          submitDisabled={!canContinue}
          error={panelDataError}
        />
      </PageShell>
    );
  }

  return (
    <EditorWorkspace
      title="Create Codebook"
      emphasis="builder"
      subtitle={
        mode === "refine"
          ? `Refining · ${totalRows} row${totalRows === 1 ? "" : "s"} total`
          : `${totalRows} row${totalRows === 1 ? "" : "s"} total`
      }
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
        </>
      }
      list={
        <CodebookSourceReader
          rows={rows}
          activeKey={activeKey}
          onSelectRow={(row) => setActiveKey(rowKey(row))}
          loading={loading}
          page={page}
          limit={limit}
          onLimitChange={setLimit}
          hasNextPage={hasNextPage}
          onPrevPage={() => setPage((p) => Math.max(0, p - 1))}
          onNextPage={() => setPage((p) => p + 1)}
          getMemo={getMemo}
        />
      }
      reader={<CodebookBuilderPane editor={editor} disabled={submitting} />}
      rail={
        <CodebookReferenceRail
          activeRow={activeRow}
          memo={activeRow ? getMemo(activeRow.rowType, activeRow.id) : null}
          onSaveMemo={saveMemo}
          database={database}
          existingCodes={editor.existingCodes}
          onProposals={editor.receiveProposals}
          disabled={submitting}
        />
      }
      actionBar={
        <EditorActionBar
          summary={
            <>
              {draftCount} code{draftCount === 1 ? "" : "s"}
              {proposed > 0 ? ` · ${proposed} awaiting review` : ""}
              {aiAccepted > 0 ? ` · ${aiAccepted} from AI` : ""}
            </>
          }
          secondaryLabel="Clear"
          onSecondary={editor.clearDraft}
          secondaryDisabled={submitting || (draftCount === 0 && proposed === 0)}
          primaryLabel="Save"
          primaryLoadingLabel="Saving..."
          primaryLoading={submitting}
          onPrimary={handleSubmit}
          primaryDisabled={!canSubmit}
          errorMessage={submitError}
        />
      }
    />
  );
}
