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
  },
};

export default function ComparePageContainer({ mode = "codebook", initialA = "", showTitle = false }) {
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
  });

  return (
    <div className="compare-page">
      {showTitle ? <h1 className="tool-page-title">{config.title}</h1> : null}

      <form onSubmit={submitCompare}>
        <div className="compare-layout-row">
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

        <div className="compare-actions-bar">
          <button
            className="project-tab compare-submit-btn"
            type="submit"
            disabled={loading}
          >
            {loading ? "Comparing..." : "Compare"}
          </button>
        </div>
      </form>

      {error && <div className="alert alert--error compare-page-alert">{error}</div>}

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
