import { useLocation } from "react-router-dom";
import ComparePageContainer from "../components/compare/ComparePageContainer";

export default function CompareCodebook() {
  const location = useLocation();

  return <ComparePageContainer mode="codebook" initialA={location.state?.codebookA || ""} />;
}
