import CompareDualSelectPanel from "./CompareDualSelectPanel";
import CompareModelPromptPanel from "./CompareModelPromptPanel";
import PageShell from "../shell/PageShell";
import { btnPrimary } from "../../lib/uiClasses";
import CompareResultPanel from "./CompareResultPanel";
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
    validationMessage: "Select two codebooks to compare",
    viewPath: "/codebook-comparison-view",
    viewStateKey: "selected",
    usesJobPolling: true,
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
    validationMessage: "Select two codings to compare",
    viewPath: "/coding-comparison-view",
    viewStateKey: "selectedCodedData",
    usesJobPolling: true,
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
    usesJobPolling: config.usesJobPolling,
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
        />
      </div>

      <form onSubmit={submitCompare} className="mt-2 border-t border-line pt-4">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-paper/70">
          AI Synthesis Narrative
        </div>
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
        />

        <div className="mt-3 flex justify-center">
          <button className={btnPrimary} type="submit" disabled={loading}>
            {loading ? "Generating AI Comparison..." : "Generate AI Comparison"}
          </button>
        </div>
      </form>

      {error && (
        <div className="border border-error bg-error/10 px-3 py-2 text-sm text-error">
          {error}
        </div>
      )}

      <CompareResultPanel
        comparison={comparison}
        createdFile={createdFile}
        viewPath={config.viewPath}
        viewStateKey={config.viewStateKey}
      />
    </PageShell>
  );
}
