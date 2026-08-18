import { useLocation } from "react-router-dom";
import ComparePageContainer from "../components/compare/ComparePageContainer";

export default function CompareCodebook() {
  const location = useLocation();

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-10">
      <ComparePageContainer mode="codebook" initialA={location.state?.codebookA || ""} />
    </div>
  );
}
