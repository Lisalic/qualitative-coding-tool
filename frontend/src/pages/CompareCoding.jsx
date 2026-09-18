import { useLocation } from "react-router-dom";
import ComparePageContainer from "../components/compare/ComparePageContainer";

export default function CompareCoding() {
  const location = useLocation();

  return <ComparePageContainer mode="coding" initialA={location.state?.codingA || ""} />;
}
