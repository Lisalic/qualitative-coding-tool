import DataBrowserPage from "../components/data/DataBrowserPage";
import useDataBrowserPage from "../components/data/useDataBrowserPage";

export default function FilteredData() {
  const page = useDataBrowserPage({ mode: "filtered" });

  return <DataBrowserPage page={page} pageTitle="View Filtered Data" />;
}
