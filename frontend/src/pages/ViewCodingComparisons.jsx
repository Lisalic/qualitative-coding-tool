import ComparisonViewPageContainer from "../components/comparisons/ComparisonViewPageContainer";

export default function ViewCodingComparisons() {
  return (
    <ComparisonViewPageContainer
      title="View Coding Comparisons"
      fileType="coding_comparison"
      preselectStateKey="selectedCodedData"
      contentUrl={(id) => `/api/coding-comparison?coding_id=${encodeURIComponent(id)}`}
      contentField="coding_comparison"
      emptyMessage="No coding comparisons available"
    />
  );
}
