import DatabaseSelectionSection from "../components/data/DatabaseSelectionSection";
import SelectedDatabaseTableSection from "../components/data/SelectedDatabaseTableSection";
import useDataBrowserPage from "../components/data/useDataBrowserPage";
import "../styles/Data.css";

export default function Data() {
  const page = useDataBrowserPage({ mode: "raw" });

  return (
    <div className={page.containerClassName}>
      <DatabaseSelectionSection page={page} />
      <SelectedDatabaseTableSection page={page} />
    </div>
  );
}
