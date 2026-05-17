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
    return <PageEmptyState className="empty-state mt-md" message={emptyMessage} />;
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
