import DatabaseSelectionSection from "../components/data/DatabaseSelectionSection";
import SelectedDatabaseTableSection from "../components/data/SelectedDatabaseTableSection";
import useDataBrowserPage from "../components/data/useDataBrowserPage";
import "../styles/Data.css";

export default function FilteredData() {
  const page = useDataBrowserPage({ mode: "filtered" });

  return (
    <div className={page.containerClassName}>
      <div className={page.cardClassName} style={{ width: "100%" }}>
        <DatabaseSelectionSection page={page} />
        <SelectedDatabaseTableSection page={page} />
      </div>
    </div>
  );
}
