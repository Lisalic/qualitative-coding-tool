import CodingProjectScopeBar from "../components/coding-table/workspace/CodingProjectScopeBar";
import ArtifactSelector from "../components/primitives/ArtifactSelector";
import useViewCodingPage from "../components/coding-table/workspace/useViewCodingPage";
import CodingWorkspaceSection from "../components/coding-table/workspace/CodingWorkspaceSection";
import ViewPageShell from "../components/shell/ViewPageShell";

export default function ViewCoding() {
  const page = useViewCodingPage();

  return (
    <ViewPageShell title="View Coding">
      <CodingProjectScopeBar page={page} />
      <ArtifactSelector
        items={page.availableCodedData}
        selectedId={page.selectedCodedData}
        onSelect={page.handleCodedDataChange}
        emptyMessage="No coded data available"
      />
      <CodingWorkspaceSection page={page} />
    </ViewPageShell>
  );
}
