import ComparisonViewPageContainer from "../components/comparisons/ComparisonViewPageContainer";

export default function ViewCodebookComparisons() {
  return (
    <ComparisonViewPageContainer
      title="View Codebook Comparisons"
      fileType="codebook_comparison"
      preselectStateKey="selected"
      contentUrl={(id) => `/api/codebook?codebook_id=${encodeURIComponent(id)}`}
      contentField="codebook"
      emptyMessage="No codebook comparisons available"
    />
  );
}
