import { useState, useEffect } from "react";
import { requestJson } from "../../api";
import FormShell from "../forms/FormShell";
import DatabaseSourceFields from "../forms/DatabaseSourceFields";
import SliderField from "../forms/SliderField";
import ContentScopeFormGroup from "../tool-panels/ContentScopeFormGroup";
import Panel from "../shell/Panel";
import { input, select } from "../../lib/uiClasses";
import { useToolPanelData } from "../tool-panels/useToolPanelData";
import { useInitialProjectId } from "../tool-panels/useInitialProjectId";
import { MissingFieldsError, buildManualCodingPayload } from "../../lib/apiContracts";

const inputClasses = input;
const selectClasses = select;

/**
 * Start a coding artifact: pick the source data, the codebook, and how
 * much of it to sample.
 *
 * Creates the artifact uncoded (`POST /api/coding/manual`) -- rows
 * copied in, codebook snapshotted, nothing tagged -- and drops the
 * researcher into the ViewCoding workspace to tag it themselves, with
 * the AI available there on whichever rows they select (select-all, then
 * Recode with AI). Coding is iterative, so this is only the setup step:
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
  const [samplePercentage, setSamplePercentage] = useState(100);
  const [contentScope, setContentScope] = useState("both");
  const {
    databases,
    filteredDatabases,
    projects,
    codebooks,
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
          projectId: selectedProject || null,
          samplePercentage,
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

  const getAvailableDatabases = () => {
    if (databaseType === "filtered") {
      return filteredDatabases.map((item) => ({
        name: item.value,
        display_name: item.label,
        metadata: item.meta,
      }));
    }
    return databases.map((item) => ({
      name: item.value,
      display_name: item.label,
      metadata: item.meta,
    }));
  };

  const getDisplayName = (item) => {
    if (!item) return "";
    if (typeof item === "object") return item.display_name || item.name || "";
    return item.replace(".db", "");
  };

  const getSelectedRecordCount = () => {
    const selected = getAvailableDatabases().find((item) => {
      const value = typeof item === "string" ? item : item.name;
      return value === database;
    });
    const tables = selected?.metadata?.tables || [];
    if (!Array.isArray(tables) || tables.length === 0) return 0;

    const hasRelevantTables = tables.some(
      (t) => t?.table_name === "submissions" || t?.table_name === "comments",
    );

    return tables.reduce((sum, t) => {
      const tableName = t?.table_name;
      if (
        hasRelevantTables &&
        tableName !== "submissions" &&
        tableName !== "comments"
      ) {
        return sum;
      }
      return sum + (Number(t?.row_count) || 0);
    }, 0);
  };

  const getTableRowCount = (tableName) => {
    const selected = getAvailableDatabases().find((item) => {
      const value = typeof item === "string" ? item : item.name;
      return value === database;
    });
    const tables = selected?.metadata?.tables || [];
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

  const databaseOptions = getAvailableDatabases().map((item) => ({
    value: typeof item === "string" ? item : item.name,
    label: getDisplayName(item),
  }));

  const projectOptions = (projects || []).map((p) => ({
    value: String(p.id),
    label: p.projectname || p.display_name || p.name || String(p.id),
  }));

  const displayError = error || panelDataError;

  return (
    <FormShell
      columns
      onSubmit={handleSubmit}
      submitButton={{
        text: "Create coding",
        loadingText: "Creating...",
        disabled: loading,
      }}
      error={displayError}
    >
      <Panel
        title="Source data & codebook"
        className="flex-1"
        scroll={false}
        bodyClassName="flex flex-col gap-3"
      >
        <DatabaseSourceFields
          radioName="apply-database-type"
          databaseType={databaseType}
          onDatabaseTypeChange={handleDatabaseTypeChange}
          database={database}
          onDatabaseChange={handleDatabaseChange}
          databaseOptions={databaseOptions}
          databasePlaceholder="Select a database"
          selectedProject={selectedProject}
          onProjectChange={setSelectedProject}
          projectOptions={projectOptions}
          disabled={loading}
        />

        <div className="flex flex-col gap-1.5">
          <label htmlFor="codebook" className="text-sm">
            Select Codebook
          </label>
          <select
            id="codebook"
            value={codebook}
            onChange={(e) => setCodebook(e.target.value)}
            className={selectClasses}
            disabled={loading}
          >
            {codebooks.length === 0 ? (
              <option value="" disabled>
                No codebooks available
              </option>
            ) : (
              codebooks.map((cb) => (
                <option key={cb.id} value={cb.id.toString()}>
                  {cb.name || cb.display_name || cb.id.toString()}
                </option>
              ))
            )}
          </select>
        </div>

        <ContentScopeFormGroup
          contentScope={contentScope}
          onContentScopeChange={setContentScope}
          postsAvailable={postsAvailable}
          commentsAvailable={commentsAvailable}
          disabled={loading || !database}
          radioName="apply-content-scope"
        />

        <SliderField
          id="samplePercentage"
          label="Sample Size"
          value={samplePercentage}
          onChange={setSamplePercentage}
          min={1}
          max={100}
          step={1}
          disabled={loading || !database}
          valueDisplay={database ? `${samplePercentage}%` : ""}
          valueMinWidth="70px"
          caption={
            !database
              ? "Select a database to see sampled record counts."
              : `${Math.ceil((getSelectedRecordCount() * samplePercentage) / 100)} of ${getSelectedRecordCount()} records will be selected randomly.`
          }
        />
      </Panel>

      <Panel
        title="Output"
        className="flex-1"
        scroll={false}
        bodyClassName="flex flex-col gap-3"
      >
        <div className="flex flex-col gap-1.5">
          <label htmlFor="report_name" className="text-sm">
            Report Name
          </label>
          <input
            id="report_name"
            type="text"
            value={reportName}
            onChange={(e) => setReportName(e.target.value)}
            placeholder="Enter report name..."
            className={inputClasses}
            disabled={loading}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="description" className="text-sm">
            Description (optional)
          </label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description for the report"
            rows={2}
            className={`${inputClasses} resize-y`}
            disabled={loading}
          />
        </div>

        <p className="text-sm text-paper/60">
          Rows come in uncoded &mdash; tag by hand, or select rows and run the AI.
        </p>
      </Panel>
    </FormShell>
  );
}
