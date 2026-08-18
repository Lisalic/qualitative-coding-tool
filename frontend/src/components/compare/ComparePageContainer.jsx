import CompareDualSelectPanel from "./CompareDualSelectPanel";
import CompareModelPromptPanel from "./CompareModelPromptPanel";
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
    resultFileType: "codebook_comparison",
    // Backend converted to the background-job pattern (Stage 7) -- see
    // useComparePageData's usesJobPolling handling.
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
    resultFileType: "coding_comparison",
    // Backend converted to the background-job pattern (Stage 8) -- see
    // useComparePageData's usesJobPolling handling.
    usesJobPolling: true,
  },
};

export default function ComparePageContainer({ mode = "codebook", initialA = "", showTitle = true }) {
  const config = CONFIG_BY_MODE[mode] || CONFIG_BY_MODE.codebook;
  const {
    items,
    a,
    b,
    setA,
    setB,
    loading,
    comparison,
    error,
    model,
    setModel,
    projects,
    additionalPrompt,
    setAdditionalPrompt,
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
    <div className="w-full">
      {showTitle ? (
        <h1 className="mb-6 text-center text-2xl font-bold">{config.title}</h1>
      ) : null}

      <form onSubmit={submitCompare}>
        <div className="flex flex-col gap-6 lg:flex-row">
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

          <CompareModelPromptPanel
            model={model}
            onModelChange={setModel}
            additionalPrompt={additionalPrompt}
            onAdditionalPromptChange={setAdditionalPrompt}
            examplePromptText={config.examplePromptText}
          />
        </div>

        <div className="mt-4 flex justify-center">
          <button
            className="border-2 border-paper px-7 py-2.5 text-base font-semibold transition-colors hover:bg-paper hover:text-ink disabled:opacity-50"
            type="submit"
            disabled={loading}
          >
            {loading ? "Comparing..." : "Compare"}
          </button>
        </div>
      </form>

      {error && (
        <div className="mt-4 border border-error bg-error/10 px-4 py-3 text-sm text-error">
          {error}
        </div>
      )}

      <CompareResultPanel
        comparison={comparison}
        fileType={config.resultFileType}
        valueA={a}
        valueB={b}
        options={items}
        projects={projects}
      />
    </div>
  );
}
