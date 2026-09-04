import ArtifactPicker from "../components/primitives/ArtifactPicker";
import useViewCodingPage from "../components/coding-table/workspace/useViewCodingPage";
import CodingWorkspaceSection from "../components/coding-table/workspace/CodingWorkspaceSection";

export default function ViewCoding() {
  const page = useViewCodingPage();

  return (
    <CodingWorkspaceSection
      page={page}
      picker={
        <ArtifactPicker
          showProjectFilter={true}
          projects={page.projectsList || []}
          selectedProject={page.selectedProject}
          onProjectChange={page.setSelectedProject}
          items={page.availableCodedData}
          selectedId={page.selectedCodedData}
          onSelect={page.handleCodedDataChange}
          emptyMessage="No coded data available"
          placeholder="Select coding…"
        />
      }
    />
  );
}
