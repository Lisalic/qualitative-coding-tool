import "../styles/Data.css";
import "../styles/DataTable.css";
import CodingProjectScopeBar from "../components/coding-table/workspace/CodingProjectScopeBar";
import ArtifactSelector from "../components/primitives/ArtifactSelector";
import useViewCodingPage from "../components/coding-table/workspace/useViewCodingPage";
import CodingWorkspaceSection from "../components/coding-table/workspace/CodingWorkspaceSection";

export default function ViewCoding() {
  const page = useViewCodingPage();

  return (
    <div className="data-container">
      <CodingProjectScopeBar page={page} />
      <ArtifactSelector
        items={page.availableCodedData}
        selectedId={page.selectedCodedData}
        onSelect={page.handleCodedDataChange}
        listClassName="codebook-selector"
        buttonClassName="db-button"
        emptyMessage="No coded data available"
      />
      <CodingWorkspaceSection page={page} />
    </div>
  );
}
