import MarkdownView from "./MarkdownView";
import PageEmptyState from "../primitives/PageEmptyState";

const ARTIFACT_CONFIG = {
  codebook: {
    fetchBase: "/api/codebook",
    queryParamName: "codebook_id",
    saveUrl: "/api/save-file-codebook/",
    saveIdFieldName: "schema_name",
    emptyLabel: "View Codebook",
    comparePath: "/compare-codebook",
    compareStateKey: "codebookA",
  },
  coding: {
    fetchBase: "/api/coded-data",
    queryParamName: "coded_id",
    saveUrl: "/api/save-file-coded-data/",
    saveIdFieldName: "schema_name",
    emptyLabel: "View Coding",
    comparePath: "/compare-coding",
    compareStateKey: "codingA",
  },
};

export default function ArtifactMarkdownSection({
  artifactType,
  selectedId,
  selectedName,
  availableItems,
  selectedSchema,
  systemPrompt,
  userPrompt,
  onSaved,
  onSelectionChangeAfterSave,
  refreshKey,
  description,
}) {
  const config = ARTIFACT_CONFIG[artifactType];
  if (!config) return null;

  if (artifactType === "codebook" && !selectedId) {
    return <PageEmptyState message="Select a codebook file to view" />;
  }

  const selectedObject = availableItems?.find(
    (item) => String(item.id) === String(selectedId),
  );
  const projectSchema =
    selectedSchema ||
    selectedObject?.metadata?.schema ||
    selectedObject?.schema_name ||
    selectedObject?.id ||
    null;

  return (
    <MarkdownView
      key={selectedId ? `${selectedId}-${refreshKey}` : `none-${refreshKey}`}
      selectedId={selectedId}
      title={selectedName}
      description={description ?? selectedObject?.description}
      fetchStyle="query"
      fetchBase={config.fetchBase}
      queryParamName={config.queryParamName}
      saveUrl={config.saveUrl}
      saveIdFieldName={config.saveIdFieldName}
      saveAsProject={true}
      projectSchema={projectSchema}
      systemPrompt={systemPrompt}
      userPrompt={userPrompt}
      comparePath={config.comparePath}
      compareStateKey={config.compareStateKey}
      onSaved={(response) => {
        onSaved?.(response);
        onSelectionChangeAfterSave?.(response);
      }}
      emptyLabel={config.emptyLabel}
    />
  );
}
