import { useState, useEffect } from "react";
import { requestJson } from "../../api";
import EditorSetupStep from "../editor-shell/EditorSetupStep";
import EditorOutputFields from "../editor-shell/EditorOutputFields";
import DatabaseSourceFields from "../forms/DatabaseSourceFields";
import ContentScopeFormGroup from "../tool-panels/ContentScopeFormGroup";
import Dropdown from "../primitives/Dropdown";
import { select } from "../../lib/uiClasses";
import { useToolPanelData } from "../tool-panels/useToolPanelData";
import { useInitialProjectId } from "../tool-panels/useInitialProjectId";
import { MissingFieldsError, buildManualCodingPayload } from "../../lib/apiContracts";

/**
 * Start a coding artifact: pick the source data, the codebook, and
 * which content types to bring in. Every row in that scope is copied
 * in -- there is no sampling step.
 *
 * Creates the artifact uncoded (`POST /api/coding/manual`) -- rows
 * copied in, codebook snapshotted, nothing tagged -- and drops the
 * researcher into the ViewCoding workspace to tag it themselves, with
 * the AI available there on whichever rows they select (select-all, then
 * Code with AI). Coding is iterative, so this is only the setup step:
 * on success it hands the new artifact to `onCreated` and its host opens
 * the coding workspace on it (see `components/coding-editor/CodingEditor.jsx`).
 */
export default function CodingSetupPanel({ onCreated }) {
  const initialProjectId = useInitialProjectId();
  const [database, setDatabase] = useState("");
  const [reportName, setReportName] = useState("");
  const [databaseType, setDatabaseType] = useState("unfiltered");
  const [codebook, setCodebook] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [description, setDescription] = useState("");
  const [selectedProject, setSelectedProject] = useState(initialProjectId);
  const [contentScope, setContentScope] = useState("both");
  const {
    databases,
    filteredDatabases,
    projects,
    codebooks,
    loading: panelDataLoading,
    error: panelDataError,
  } = useToolPanelData({ includeCodebooks: true });

  useEffect(() => {
    setCodebook((prev) => {
      if (prev) return prev;
      if (codebooks.length > 0) return String(codebooks[0].id);
      return prev;
    });
  }, [codebooks]);

  const handleSubmit = async () => {
    if (codebooks.length === 0) {
      setError("No codebooks available. Please create a codebook first.");
      return;
    }
    try {
      setLoading(true);
      setError(null);

      let payload;
      try {
        payload = buildManualCodingPayload({
          database,
          codebook,
          reportName,
          description,
          projectId: selectedProject,
          contentScope,
        });
      } catch (err) {
        if (err instanceof MissingFieldsError) {
          setError(err.message);
          return;
        }
        throw err;
      }

      const { ok, data, error: postError } = await requestJson("/api/coding/manual", {
        method: "POST",
        body: payload,
      });
      if (!ok) {
        setError(postError || "Failed to start the coding");
        return;
      }

      onCreated(data?.file);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // `useToolPanelData` already returns `{value,label,meta}` -- the shape
  // Dropdown wants -- so these are passed through rather than remapped.
  const databaseOptions = databaseType === "filtered" ? filteredDatabases : databases;

  const codebookOptions = codebooks.map((cb) => ({
    value: cb.id.toString(),
    label: cb.name || cb.display_name || cb.id.toString(),
  }));

  const getTableRowCount = (tableName) => {
    const selected = databaseOptions.find((item) => item.value === database);
    const tables = selected?.meta?.tables || [];
    const table = tables.find((t) => t?.table_name === tableName);
    return Number(table?.row_count) || 0;
  };

  const handleDatabaseTypeChange = (type) => {
    setDatabaseType(type);
    setDatabase("");
    setContentScope("both");
  };

  const handleDatabaseChange = (value) => {
    setDatabase(value);
    setContentScope("both");
  };

  const postsAvailable = getTableRowCount("submissions") > 0;
  const commentsAvailable = getTableRowCount("comments") > 0;

  useEffect(() => {
    // Auto-select the only content type that actually has rows, so a
    // posts-only (or comments-only) database doesn't default to a "both"
    // scope that silently samples nothing from the missing table.
    if (!postsAvailable && commentsAvailable && contentScope !== "comments") {
      setContentScope("comments");
    } else if (
      postsAvailable &&
      !commentsAvailable &&
      contentScope !== "posts"
    ) {
      setContentScope("posts");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [postsAvailable, commentsAvailable]);

  const displayError = error || panelDataError;
  const canSubmit =
    !loading &&
    Boolean(database) &&
    Boolean(codebook) &&
    Boolean(reportName.trim()) &&
    Boolean(selectedProject);

  return (
    <EditorSetupStep
      sourceTitle="Source data & codebook"
      sourceFields={
        <>
          <DatabaseSourceFields
            radioName="apply-database-type"
            databaseType={databaseType}
            onDatabaseTypeChange={handleDatabaseTypeChange}
            database={database}
            onDatabaseChange={handleDatabaseChange}
            databaseOptions={databaseOptions}
            databasePlaceholder={panelDataLoading ? "Loading..." : "Select a database"}
            disabled={loading}
          />

          <div className="flex flex-col gap-1.5">
            <label htmlFor="codebook" className="text-sm">
              Select Codebook
            </label>
            <Dropdown
              id="codebook"
              value={codebook}
              options={codebookOptions}
              onChange={setCodebook}
              placeholder="Select a codebook"
              disabled={loading}
              triggerClassName={`w-full ${select}`}
              listLabel="Codebook"
              searchPlaceholder="Search codebooks…"
              emptyMessage={
                codebooks.length === 0
                  ? "No codebooks available."
                  : "No codebooks match that search."
              }
            />
          </div>

          <ContentScopeFormGroup
            contentScope={contentScope}
            onContentScopeChange={setContentScope}
            postsAvailable={postsAvailable}
            commentsAvailable={commentsAvailable}
            disabled={loading || !database}
            radioName="apply-content-scope"
          />
        </>
      }
      outputFields={
        <>
          <EditorOutputFields
            idPrefix="codingSetup"
            name={reportName}
            onNameChange={setReportName}
            namePlaceholder="Enter report name..."
            nameLabel="Report Name"
            description={description}
            onDescriptionChange={setDescription}
            selectedProject={selectedProject}
            onProjectChange={setSelectedProject}
            projectOptions={projects}
            disabled={loading}
          />
        </>
      }
      onSubmit={handleSubmit}
      submitLabel="Create coding"
      submitLoadingLabel="Creating..."
      submitDisabled={!canSubmit}
      submitLoading={loading}
      error={displayError}
    />
  );
}
