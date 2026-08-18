import DataTable from "./DataTable";
import PageEmptyState from "../primitives/PageEmptyState";

export default function SelectedDatabaseTableSection({ page }) {
  const {
    selectedDatabase,
    title,
    displayName,
    selectedMetadata,
    selectedDescription,
    tableProps = {},
  } = page;
  const { isFilteredView = false, emptyMessage } = tableProps;

  if (!selectedDatabase) {
    return (
      <PageEmptyState
        className="mt-4 border border-paper/20 bg-white/[0.02] px-4 py-6 text-center italic text-paper/70"
        message={emptyMessage}
      />
    );
  }

  return (
    <DataTable
      title={title}
      database={selectedDatabase}
      isFilteredView={isFilteredView}
      displayName={displayName}
      metadata={selectedMetadata}
      description={selectedDescription}
    />
  );
}
