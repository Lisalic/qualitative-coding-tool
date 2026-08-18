import { useLocation } from "react-router-dom";
import ComparePageContainer from "../components/compare/ComparePageContainer";

export default function CompareCoding() {
  const location = useLocation();

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-10">
      <ComparePageContainer mode="coding" initialA={location.state?.codingA || ""} />
    </div>
  );
}
