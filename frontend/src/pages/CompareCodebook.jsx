import { useLocation } from "react-router-dom";
import ComparePageContainer from "../components/compare/ComparePageContainer";
import ToolPage from "../components/shell/ToolPage";
import "../styles/Home.css";

export default function CompareCodebook() {
  const location = useLocation();

  return (
    <ToolPage bodyProps={{ className: "single-panel-layout compare-page-shell" }}>
      <ComparePageContainer mode="codebook" initialA={location.state?.codebookA || ""} />
    </ToolPage>
  );
}
