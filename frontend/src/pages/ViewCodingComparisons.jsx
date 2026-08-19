import ComparisonViewPageContainer from "../components/comparisons/ComparisonViewPageContainer";

export default function ViewCodingComparisons() {
  return (
    <ComparisonViewPageContainer
      title="View Coding Comparisons"
      fileType="coding_comparison"
      preselectStateKey="selectedCodedData"
      contentUrl={(id) => `/api/coded-data?coded_id=${encodeURIComponent(id)}`}
      contentField="coded_data"
      emptyMessage="No coding comparisons available"
    />
  );
}
