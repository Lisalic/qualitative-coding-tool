import DatabaseSelectionSection from "../components/data/DatabaseSelectionSection";
import SelectedDatabaseTableSection from "../components/data/SelectedDatabaseTableSection";
import useDataBrowserPage from "../components/data/useDataBrowserPage";
import ViewPageShell from "../components/shell/ViewPageShell";

export default function FilteredData() {
  const page = useDataBrowserPage({ mode: "filtered" });

  return (
    <ViewPageShell title="View Filtered Data">
      <DatabaseSelectionSection page={page} />
      <SelectedDatabaseTableSection page={page} />
    </ViewPageShell>
  );
}
