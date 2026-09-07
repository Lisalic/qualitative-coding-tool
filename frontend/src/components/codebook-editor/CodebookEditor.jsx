import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch, requestJson } from "../../api";
import CodeLegend from "../coding-table/CodeLegend";
import EntryModal from "../data/EntryModal";
import { useRowMemos } from "../data/useRowMemos";
import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";
import PageShell from "../shell/PageShell";
import Panel from "../shell/Panel";
import { useInitialProjectId } from "../tool-panels/useInitialProjectId";
import { useToolPanelData } from "../tool-panels/useToolPanelData";
import {
  MissingFieldsError,
  buildManualCodebookPayload,
} from "../../lib/apiContracts";
import { flattenTreeToCodes, getCodeColor, groupCodesByFamily } from "../../lib/codingUtils";
import { btn, btnActive, btnPrimary, input, select } from "../../lib/uiClasses";
import CodebookAiPanel from "./CodebookAiPanel";
import CodebookProposalTray from "./CodebookProposalTray";
import CodebookSourceReader from "./CodebookSourceReader";
import { useCodebookEditorState } from "./useCodebookEditorState";

const PROJ_SCHEMA_RE = /^proj_[A-Za-z0-9_]+$/;

const noop = () => {};

function StepHeading({ number, title, description }) {
  return (
    <div className="flex items-start gap-3">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center border border-paper text-xs font-bold">
        {number}
      </span>
      <div>
        <h2 className="text-sm font-semibold">{title}</h2>
        {description ? <p className="mt-0.5 text-xs text-paper/60">{description}</p> : null}
      </div>
    </div>
  );
}

/**
 * Write a codebook by hand, with the data in front of you.
 *
 * The human-in-the-loop counterpart of `/codebook-generate`: instead of
 * writing a prompt and receiving a finished codebook, the researcher reads
 * the source corpus on the left and builds the code list on the right,
 * with the generator available inside the screen as an assistant whose
 * codes arrive in a review tray (`CodebookProposalTray`) rather than in
 * the codebook. Nothing is created or saved until an explicit submit.
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

  const [selectedEntry, setSelectedEntry] = useState(null);
  const [showModal, setShowModal] = useState(false);

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

  const openRow = (row, rowType) => {
    setSelectedEntry({ ...row, type: rowType });
    setShowModal(true);
  };

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
    <PageShell title="Codebook Editor" width="full" bodyClassName="flex flex-col gap-3">
      <section className="flex flex-col gap-3 border border-line bg-surface p-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <StepHeading
            number="1"
            title="Choose what you're building"
            description="Read the data on the left, write the codebook on the right."
          />
          <div className="flex gap-2" role="group" aria-label="Editor mode">
            <button
              type="button"
              className={`${btn} ${mode === "new" ? btnActive : ""}`}
              aria-pressed={mode === "new"}
              onClick={() => setMode("new")}
              disabled={submitting}
            >
              New codebook
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
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="flex flex-col gap-1.5">
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

          {mode === "refine" ? (
            <div className="flex flex-col gap-1.5">
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
          ) : (
            <div className="flex flex-col gap-1.5">
              <label htmlFor="codebookEditorName" className="text-sm">
                Codebook name
              </label>
              <input
                id="codebookEditorName"
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="my-codebook"
                className={input}
                disabled={submitting}
              />
            </div>
          )}

          {mode === "new" ? (
            <>
              <div className="flex flex-col gap-1.5 md:col-span-2">
                <label htmlFor="codebookEditorDescription" className="text-sm">
                  Description (optional)
                </label>
                <textarea
                  id="codebookEditorDescription"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="Optional description for the codebook"
                  rows={2}
                  className={`${input} w-full resize-y`}
                  disabled={submitting}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="codebookEditorProject" className="text-sm">
                  Project (optional)
                </label>
                <select
                  id="codebookEditorProject"
                  value={selectedProject || ""}
                  onChange={(event) => setSelectedProject(event.target.value)}
                  className={select}
                  disabled={submitting}
                >
                  <option value="">No project</option>
                  {(projects || []).map((project) => (
                    <option key={project.id} value={String(project.id)}>
                      {project.projectname}
                    </option>
                  ))}
                </select>
              </div>
            </>
          ) : null}
        </div>
      </section>

      {error || panelDataError ? (
        <p className="border border-error bg-error/10 px-3 py-2 text-sm text-error">
          {error || panelDataError}
        </p>
      ) : null}

      {savedMessage ? (
        <p role="status" className="border border-success bg-success/10 px-3 py-2 text-sm text-success">
          {savedMessage}
        </p>
      ) : null}

      {createdFile ? (
        <ArtifactCreatedMessage
          name={createdFile.filename}
          viewPath="/codebook-view"
          viewState={{ selected: createdFile.schema_name }}
        />
      ) : null}

      {!database ? (
        <section className="border border-line bg-surface p-6 text-center text-sm text-paper/60">
          Select a source database to start reading and coding.
        </section>
      ) : (
        <div className="grid grid-cols-1 items-start gap-3 lg:grid-cols-2">
          <CodebookSourceReader
            entries={entries}
            loading={loading}
            page={page}
            limit={limit}
            onPageChange={setPage}
            onLimitChange={(next) => {
              setLimit(next);
              setPage(0);
            }}
            getMemo={getMemo}
            onOpenRow={openRow}
          />

          <div className="flex flex-col gap-3">
            <Panel title={`Draft codes (${draftCount})`} padded={false}>
              <CodeLegend
                codebookTree={editor.draft}
                isEditMode
                draftTree={editor.draft}
                onDraftTreeChange={editor.updateDraft}
                disabled={submitting}
                selectedFilterCodes={[]}
                onCodeToggle={noop}
                getCodeColor={getCodeColor}
                showDetails
              />
            </Panel>

            <CodebookProposalTray
              proposals={editor.proposals}
              onAccept={editor.accept}
              onDismiss={editor.dismiss}
              onAcceptAll={editor.acceptEvery}
              onDismissAll={editor.dismissEvery}
              disabled={submitting}
            />

            <CodebookAiPanel
              database={database}
              existingCodes={editor.existingCodes}
              onProposals={editor.receiveProposals}
              disabled={submitting}
            />
          </div>
        </div>
      )}

      {database ? (
        <div className="sticky bottom-0 z-20 flex flex-wrap items-center justify-between gap-3 border border-line bg-surface px-3 py-2">
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
              Clear draft
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
      ) : null}

      <EntryModal
        entry={selectedEntry}
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        database={database}
        memo={
          selectedEntry ? getMemo(selectedEntry.type, selectedEntry.id) : null
        }
        onSaveMemo={
          selectedEntry
            ? (body) => saveMemo(selectedEntry.type, selectedEntry.id, body)
            : null
        }
      />
    </PageShell>
  );
}
