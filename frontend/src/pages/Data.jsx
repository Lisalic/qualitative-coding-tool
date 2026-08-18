import DatabaseSelectionSection from "../components/data/DatabaseSelectionSection";
import SelectedDatabaseTableSection from "../components/data/SelectedDatabaseTableSection";
import useDataBrowserPage from "../components/data/useDataBrowserPage";
import ViewPageShell from "../components/shell/ViewPageShell";

export default function Data() {
  const page = useDataBrowserPage({ mode: "raw" });

  return (
    <ViewPageShell title="View Data">
      <DatabaseSelectionSection page={page} />
      <SelectedDatabaseTableSection page={page} />
    </ViewPageShell>
  );
}
