import DataBrowserPage from "../components/data/DataBrowserPage";
import useDataBrowserPage from "../components/data/useDataBrowserPage";

export default function Data() {
  const page = useDataBrowserPage({ mode: "raw" });

  return <DataBrowserPage page={page} pageTitle="View Data" />;
}
