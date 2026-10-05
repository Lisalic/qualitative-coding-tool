import CompareDualSelectPanel from "./CompareDualSelectPanel";
import CompareModelPromptPanel from "./CompareModelPromptPanel";
import PageShell from "../shell/PageShell";
import { btnPrimary, meta } from "../../lib/uiClasses";
import CompareResultPanel from "./CompareResultPanel";
import ErrorDisplay from "../feedback/ErrorDisplay";
import ProgressBar from "../feedback/ProgressBar";
import useComparePageData from "./useComparePageData";

const CONFIG_BY_MODE = {
  codebook: {
    title: "Compare Codebook",
    panelTitle: "Select codebooks",
    labelA: "Codebook A",
    labelB: "Codebook B",
    placeholderOption: "Select a codebook",
    examplePromptText:
      "Please provide a detailed comparison focusing on:\n- Key differences in coding approaches\n- Overlapping themes and codes\n- Unique insights from each codebook\n- Recommendations for merging or refining the codebooks",
    fileType: "codebook",
    compareEndpoint: "/api/compare-codebooks/",
    fieldAName: "codebook_a",
    fieldBName: "codebook_b",
    validationMessage: "Choose a codebook.",
    viewPath: "/codebook-comparison-view",
    viewStateKey: "selected",
  },
  coding: {
    title: "Compare Coding",
    panelTitle: "Select codings",
    labelA: "Coding A",
    labelB: "Coding B",
    placeholderOption: "Select a coding",
    examplePromptText:
      "Please provide a detailed comparison focusing on:\n- Differences in coding decisions and interpretations\n- Patterns of agreement and disagreement\n- Quality and consistency of coding applications\n- Recommendations for improving coding reliability",
    fileType: "coding",
    compareEndpoint: "/api/compare-codings/",
    fieldAName: "coding_a",
    fieldBName: "coding_b",
    validationMessage: "Choose a coding.",
    viewPath: "/coding-comparison-view",
    viewStateKey: "selectedCodedData",
  },
};

export default function ComparePageContainer({
  mode = "codebook",
  initialA = "",
  showTitle = true,
}) {
  const config = CONFIG_BY_MODE[mode] || CONFIG_BY_MODE.codebook;
  const {
    items,
    a,
    b,
    setA,
    setB,
    loading,
    comparison,
    createdFile,
    error,
    fieldErrors,
    progress,
    partialNote,
    listError,
    model,
    setModel,
    name,
    setName,
    additionalPrompt,
    setAdditionalPrompt,
    projects,
    selectedProject,
    setSelectedProject,
    submitCompare,
  } = useComparePageData({
    fileType: config.fileType,
    compareEndpoint: config.compareEndpoint,
    fieldAName: config.fieldAName,
    fieldBName: config.fieldBName,
    initialA,
    validationMessage: config.validationMessage,
  });

  return (
    <PageShell
      title={showTitle ? config.title : undefined}
      width="wide"
      bodyClassName="flex flex-col gap-3"
    >
      <div className="flex flex-col gap-3">
        <CompareDualSelectPanel
          panelTitle={config.panelTitle}
          labelA={config.labelA}
          labelB={config.labelB}
          placeholderOption={config.placeholderOption}
          options={items}
          valueA={a}
          valueB={b}
          onChangeA={setA}
          onChangeB={setB}
          errors={fieldErrors}
        />
        <ErrorDisplay message={listError} variant="alert" />
      </div>

      <form onSubmit={submitCompare} className="flex flex-col gap-3">
        <CompareModelPromptPanel
          model={model}
          onModelChange={setModel}
          name={name}
          onNameChange={setName}
          projects={projects}
          selectedProject={selectedProject}
          onProjectChange={setSelectedProject}
          additionalPrompt={additionalPrompt}
          onAdditionalPromptChange={setAdditionalPrompt}
          examplePromptText={config.examplePromptText}
          errors={fieldErrors}
        />

        <div className="flex flex-col items-center gap-1.5">
          <button className={btnPrimary} type="submit" disabled={loading}>
            {loading ? "Comparing…" : "Compare"}
          </button>
          {loading ? (
            <p className={meta}>
              This can take a few minutes. If you leave, it keeps running and the comparison will
              appear in your project.
            </p>
          ) : null}
        </div>
      </form>

      {loading && progress ? (
        <ProgressBar current={progress.current} total={progress.total} label={progress.label} />
      ) : null}

      <ErrorDisplay message={error} variant="alert" />

      <CompareResultPanel
        comparison={comparison}
        createdFile={createdFile}
        viewPath={config.viewPath}
        viewStateKey={config.viewStateKey}
        partialNote={partialNote}
      />
    </PageShell>
  );
}
