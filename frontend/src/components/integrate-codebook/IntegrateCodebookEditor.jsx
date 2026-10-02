import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import { requestJson } from "../../api";
import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";
import ErrorDisplay from "../feedback/ErrorDisplay";
import PageShell from "../shell/PageShell";
import { useInitialProjectId } from "../tool-panels/useInitialProjectId";
import { useToolPanelData } from "../tool-panels/useToolPanelData";
import {
  MissingFieldsError,
  buildIntegrateCodebookPayload,
} from "../../lib/apiContracts";
import { integrateDraftStorageKey } from "../../lib/codebookEditorState";
import { flattenTreeToCodes } from "../../lib/codingUtils";
import { btn } from "../../lib/uiClasses";
import { useCodebookEditorState } from "../codebook-editor/useCodebookEditorState";
import EditorSetupStep from "../editor-shell/EditorSetupStep";
import EditorOutputFields from "../editor-shell/EditorOutputFields";
import EditorWorkspace from "../editor-shell/EditorWorkspace";
import EditorActionBar from "../editor-shell/EditorActionBar";
import IntegrateBuilderPane from "./IntegrateBuilderPane";
import IntegrateRail from "./IntegrateRail";
import IntegrateSourcePane from "./IntegrateSourcePane";
import IntegrateSourcePicker from "./IntegrateSourcePicker";
import { useSourceCodebooks } from "./useSourceCodebooks";
import { useSourceComparisons } from "./useSourceComparisons";

/**
 * Merge two or more existing codebooks into one, with the source codes
 * in front of you.
 *
 * Same two-step shape as Create Codebook: a setup step picks the source
 * codebooks (two or more) and names the output, then a 3-pane workspace
 * opens -- the source codebooks' codes on the left (read-only, grouped
 * by codebook, each with an "Add" rescue action), the merged draft in
 * the center (`IntegrateBuilderPane`, built on the same `CodeLegend`
 * every other codebook editor uses), and the active source code's full
 * text plus the AI merge assistant in a reference rail on the right.
 * The rail's Comparison tab shows any Compare Codebook report made from
 * these sources -- compare-then-integrate is the intended workflow --
 * and can hand that report to the assistant as merge guidance.
 *
 * The draft starts empty: nothing is in the merged codebook until the
 * researcher accepts an AI-proposed merge or copies a source code by
 * hand, and nothing is created at all until an explicit submit --
 * mirrors Create Codebook's "review tray, never auto-write" contract,
 * see `lib/codebookEditorState.js`'s module docstring for why this
 * editor reuses that state machine rather than a second one.
 *
 * Unlike Create Codebook there is no Refine mode and no source-database
 * row list -- a merge output is always a fresh codebook, and its
 * "source data" is the codebooks themselves, not raw rows.
 */
export default function IntegrateCodebookEditor() {
  const location = useLocation();
  const initialProjectId = useInitialProjectId();
  const { codebooks, projects, loading: panelDataLoading, error: panelDataError } =
    useToolPanelData({ includeCodebooks: true });

  const [started, setStarted] = useState(false);
  // Arriving from View Codebook's "Integrate" button pre-selects that
  // codebook as the first of the set; the researcher still has to pick
  // at least one more before Continue is enabled.
  const [selectedRefs, setSelectedRefs] = useState(() =>
    location.state?.codebookA ? [location.state.codebookA] : [],
  );
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedProject, setSelectedProject] = useState(initialProjectId);

  const [activeCode, setActiveCode] = useState(null);
  const [railTab, setRailTab] = useState("code");
  const [selectedComparison, setSelectedComparison] = useState(null);
  const [useComparisonInAi, setUseComparisonInAi] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [createdFile, setCreatedFile] = useState(null);

  const codebookOptions = useMemo(
    () => (codebooks || []).filter((entry) => entry?.metadata?.file_type !== "codebook_comparison"),
    [codebooks],
  );
  const codebookNames = useMemo(() => {
    const names = {};
    for (const option of codebookOptions) {
      names[option.metadata?.schema || option.id] = option.name;
    }
    return names;
  }, [codebookOptions]);

  const storageKey = selectedRefs.length >= 2 ? integrateDraftStorageKey(selectedRefs) : "";
  const editor = useCodebookEditorState(storageKey);

  const { sources, loading: sourcesLoading, error: sourcesError } = useSourceCodebooks(
    started ? selectedRefs : [],
  );
  const { comparisons, loading: comparisonsLoading } = useSourceComparisons(started ? selectedRefs : []);

  // Open on the comparison when one covers the selection -- reading it is
  // the natural first step of a merge. Re-evaluated whenever the source
  // set (and therefore the comparison list) changes.
  useEffect(() => {
    const best = comparisons.find((c) => c.coversSelection) || null;
    setSelectedComparison(best?.ref || null);
    setUseComparisonInAi(true);
    setRailTab(best ? "comparison" : "code");
  }, [comparisons]);

  const selectCode = (code) => {
    setActiveCode(code);
    setRailTab("code");
  };

  const toggleRef = (ref) => {
    setSelectedRefs((prev) => (prev.includes(ref) ? prev.filter((r) => r !== ref) : [...prev, ref]));
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    setSubmitError("");
    setCreatedFile(null);
    const codes = flattenTreeToCodes(editor.draft);
    try {
      let payload;
      try {
        payload = buildIntegrateCodebookPayload({
          codebooks: selectedRefs,
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

      const { ok, data, error: postError } = await requestJson("/api/codebook/integrate", {
        method: "POST",
        body: payload,
      });
      if (!ok) {
        setSubmitError(postError || "Failed to create the codebook");
        return;
      }

      setCreatedFile(data?.file || null);
      // The draft has become an artifact -- starting the next merge from
      // the same selection would otherwise inherit every code just saved.
      editor.clearDraft();
    } catch (err) {
      setSubmitError(err?.message || "Failed to save the codebook");
    } finally {
      setSubmitting(false);
    }
  };

  const { draft: draftCount, proposed, aiAccepted } = editor.counts;
  const outputReady = Boolean(name.trim()) && Boolean(selectedProject);
  const canContinue = selectedRefs.length >= 2 && outputReady;
  const canSubmit = !submitting && draftCount > 0;

  const totalSourceCodes = sources.reduce((sum, s) => sum + s.codes.length, 0);

  if (!started) {
    return (
      <PageShell title="Integrate Codebook" width="wide">
        <EditorSetupStep
          sourceTitle="Source codebooks"
          sourceFields={
            <>
              <IntegrateSourcePicker
                codebooks={codebookOptions}
                selected={selectedRefs}
                onToggle={toggleRef}
                loading={panelDataLoading}
                disabled={false}
              />
              {selectedRefs.length < 2 && (
                <p className="text-sm text-paper/50">Select 2 or more codebooks to continue.</p>
              )}
            </>
          }
          outputTitle="Output"
          outputFields={
            <EditorOutputFields
              idPrefix="integrateCodebook"
              name={name}
              onNameChange={setName}
              namePlaceholder="integrated-codebook"
              nameLabel="Codebook name"
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
          submitDisabled={!canContinue}
          error={panelDataError}
        />
      </PageShell>
    );
  }

  return (
    <EditorWorkspace
      title="Integrate Codebook"
      emphasis="builder"
      subtitle={`${selectedRefs.length} codebooks · ${totalSourceCodes} codes`}
      actions={
        <button type="button" className={btn} onClick={() => setStarted(false)}>
          Change sources
        </button>
      }
      banners={
        <>
          {sourcesError && (
            <div className="shrink-0">
              <ErrorDisplay message={sourcesError} variant="alert" />
            </div>
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
        <IntegrateSourcePane
          sources={sources}
          codebookNames={codebookNames}
          loading={sourcesLoading}
          activeKey={activeCode?.key}
          onSelectCode={selectCode}
          draftCount={draftCount}
          onCopyCode={editor.copyCode}
          disabled={submitting}
        />
      }
      reader={<IntegrateBuilderPane editor={editor} codebookNames={codebookNames} disabled={submitting} />}
      rail={
        <IntegrateRail
          tab={railTab}
          onTabChange={setRailTab}
          comparisons={comparisons}
          comparisonsLoading={comparisonsLoading}
          selectedComparison={selectedComparison}
          onSelectComparison={setSelectedComparison}
          useComparisonInAi={useComparisonInAi}
          onUseComparisonInAiChange={setUseComparisonInAi}
          active={activeCode}
          codebookName={activeCode ? codebookNames[activeCode.source.ref] : ""}
          codebooks={selectedRefs}
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
          primaryLabel="Create codebook"
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
