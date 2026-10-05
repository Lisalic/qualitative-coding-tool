import ComparisonViewPageContainer from "../components/comparisons/ComparisonViewPageContainer";

export default function ViewCodingComparisons() {
  return (
    <ComparisonViewPageContainer
      title="View Coding Comparison"
      fileType="coding_comparison"
      preselectStateKey="selectedCodedData"
      contentUrl={(id) => `/api/coding-comparison?coding_id=${encodeURIComponent(id)}`}
      contentField="coding_comparison"
      emptyMessage="No coding comparisons available"
      placeholderMessage="Select a coding comparison to view its differences"
      pickerPlaceholder="Select coding comparison…"
    />
  );
}
