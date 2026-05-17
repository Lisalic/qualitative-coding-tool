import SaveSummarySection from "./SaveSummarySection";
import MarkdownDisplay from "../primitives/MarkdownDisplay";

export default function SummaryOutputSection({
  summary,
  projects,
  selectedProject,
  onProjectChange,
  saveName,
  onSaveNameChange,
  saveDescription,
  onSaveDescriptionChange,
  onSave,
  saving,
  saveSuccess,
  saveError,
}) {
  if (summary === "") return null;

  return (
    <>
      <MarkdownDisplay
        content={summary}
        title="Summary Result"
        style={{ marginTop: 16 }}
        titleStyle={{ margin: 0 }}
        innerStyle={{
          marginTop: 8,
          padding: 16,
          backgroundColor: "#000000",
          border: "1px solid #ffffff",
          borderRadius: 8,
          maxHeight: 600,
          overflow: "auto",
          whiteSpace: "pre-wrap",
          fontFamily: "monospace",
          fontSize: "14px",
          lineHeight: 1.5,
        }}
      />
      <SaveSummarySection
        projects={projects}
        selectedProject={selectedProject}
        onProjectChange={onProjectChange}
        saveName={saveName}
        onSaveNameChange={onSaveNameChange}
        saveDescription={saveDescription}
        onSaveDescriptionChange={onSaveDescriptionChange}
        onSave={onSave}
        saving={saving}
        saveSuccess={saveSuccess}
        saveError={saveError}
      />
    </>
  );
}
