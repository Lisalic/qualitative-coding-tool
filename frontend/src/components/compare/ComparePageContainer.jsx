import CompareDualSelectPanel from "./CompareDualSelectPanel";
import PageShell from "../shell/PageShell";
import ComputedComparisonResults from "./ComputedComparisonResults";
import useComparePageData from "./useComparePageData";

const CONFIG_BY_MODE = {
  codebook: {
    title: "Compare Codebook",
    panelTitle: "Select codebooks",
    labelA: "Codebook A",
    labelB: "Codebook B",
    placeholderOption: "Select a codebook",
    fileType: "codebook",
  },
  coding: {
    title: "Compare Coding",
    panelTitle: "Select codings",
    labelA: "Coding A",
    labelB: "Coding B",
    placeholderOption: "Select a coding",
    fileType: "coding",
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
    computedData,
    computedLoading,
    computedError,
    handleSwap,
  } = useComparePageData({
    fileType: config.fileType,
    initialA,
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

        {/* Computed deterministic comparison is the sole comparison path */}
        {(computedData || computedLoading || computedError) && (
          <ComputedComparisonResults
            mode={mode}
            data={computedData}
            loading={computedLoading}
            error={computedError}
            onSwap={handleSwap}
          />
        )}
      </div>
    </PageShell>
  );
}
