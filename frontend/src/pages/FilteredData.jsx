import DataBrowserPage from "../features/data/DataBrowserPage";
import useDataBrowserPage from "../features/data/useDataBrowserPage";

export default function FilteredData() {
  const page = useDataBrowserPage({ mode: "filtered" });

  return <DataBrowserPage page={page} pageTitle="View Filtered Data" />;
}
