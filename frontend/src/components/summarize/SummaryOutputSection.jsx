import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";

export default function SummaryOutputSection({ summary, createdFile }) {
  if (summary === "" || !createdFile) return null;

  return (
    <div>
      <ArtifactCreatedMessage
        name={createdFile.filename}
        viewPath="/summaryview"
        viewState={{ selectedSummary: createdFile.schema_name }}
      />
    </div>
  );
}
