import DataBrowserPage from "../features/data/DataBrowserPage";
import useDataBrowserPage from "../features/data/useDataBrowserPage";

export default function Data() {
  const page = useDataBrowserPage({ mode: "raw" });

  return <DataBrowserPage page={page} pageTitle="View Data" />;
}
