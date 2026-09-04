import { useState, useEffect } from "react";
import { postFormAndPoll } from "../../api";
import FormShell from "../forms/FormShell";
import DatabaseSourceFields from "../forms/DatabaseSourceFields";
import SliderField from "../forms/SliderField";
import PromptTextareaWithActions from "../forms/PromptTextareaWithActions";
import AiModelFormGroup from "../models/AiModelFormGroup";
import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";
import ProgressBar from "../feedback/ProgressBar";
import ContentScopeFormGroup from "./ContentScopeFormGroup";
import Panel from "../shell/Panel";
import { input, select } from "../../lib/uiClasses";
import { useToolPanelData } from "./useToolPanelData";
import { useInitialProjectId } from "./useInitialProjectId";
import {
  EXAMPLE_PROMPTS,
  MissingFieldsError,
  buildApplyCodebookForm,
} from "../../lib/apiContracts";

const EXAMPLE_PROMPT = EXAMPLE_PROMPTS.apply;
const inputClasses = input;
const selectClasses = select;

export default function ApplyCodebookPanel({
  methodology,
  onMethodologyChange,
}) {
  const initialProjectId = useInitialProjectId();
  const [database, setDatabase] = useState("");
  const [reportName, setReportName] = useState("");
  const [databaseType, setDatabaseType] = useState("unfiltered");
  const [codebook, setCodebook] = useState("");
  const [loading, setLoading] = useState(false);
  const [createdFile, setCreatedFile] = useState(null);
  const [progress, setProgress] = useState(null);
  const [partialWarning, setPartialWarning] = useState("");
  const [codingSummary, setCodingSummary] = useState("");
  const [error, setError] = useState(null);
  const [description, setDescription] = useState("");
  const [selectedProject, setSelectedProject] = useState(initialProjectId);
  const [saveMessage, setSaveMessage] = useState("");
  const [saveMessageType, setSaveMessageType] = useState("success");
  const [model, setModel] = useState("");
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
    const savedApiKey = localStorage.getItem("apiKey");
    if (!savedApiKey) {
      setError("Please set your API key in the navbar first.");
      return;
    }
    if (codebooks.length === 0) {
      setError("No codebooks available. Please create a codebook first.");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      setCreatedFile(null);
      setProgress(null);
      setPartialWarning("");
      setCodingSummary("");

      let requestData;
      try {
        requestData = buildApplyCodebookForm({
          apiKey: savedApiKey,
          database,
          codebook,
          reportName,
          methodology,
          model,
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

      const {
        ok,
        data,
        error: postError,
      } = await postFormAndPoll("/api/apply-codebook/", requestData, {
        onProgress: setProgress,
      });

      if (!ok) {
        setError(postError || "Failed to apply codebook");
        return;
      }
      setCreatedFile(data?.file || null);
      if (data?.partial) {
        const reason = data.partial_error
          ? `Stopped early after an error: ${data.partial_error}`
          : "This is likely due to a free model's batch limit -- use a paid model or reduce the sample size for complete coverage.";
        setPartialWarning(
          `Warning: only ${data.batches_processed}/${data.batches_total} batches were coded. ${reason}`,
        );
      }
      const rejectedTotal =
        (data?.rejected_unknown_item || 0) +
        (data?.rejected_unknown_code || 0) +
        (data?.rejected_quote_not_found || 0);
      if (rejectedTotal > 0) {
        setCodingSummary(
          `${data.accepted || 0} coding${data.accepted === 1 ? "" : "s"} saved. ` +
            `${rejectedTotal} rejected as unverifiable (couldn't be matched back to the source text) and were not saved.`,
        );
      }
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

  const handlePromptSaveFeedback = ({ type, message }) => {
    setSaveMessage(message);
    setSaveMessageType(type);
    setTimeout(() => setSaveMessage(""), type === "success" ? 3000 : 4000);
  };

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
    <div className="flex flex-col gap-3">
      <FormShell
        columns
        onSubmit={handleSubmit}
        submitButton={{
          text: "Apply Codebook",
          loadingText: "Applying...",
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
          title="Output & instructions"
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
              placeholder="Enter report name... "
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

          <PromptTextareaWithActions
            id="methodology"
            label="Enter Prompt"
            value={methodology}
            onChange={onMethodologyChange}
            placeholder="Enter your coding methodology or leave blank..."
            rows={2}
            promptType="apply"
            exampleText={EXAMPLE_PROMPT}
            disabled={loading}
            onSaveFeedback={handlePromptSaveFeedback}
          />

          <AiModelFormGroup
            model={model}
            onModelChange={setModel}
            disabled={loading}
            selectPlaceholder="dash"
          />
        </Panel>
      </FormShell>

      {loading && progress && (
        <ProgressBar
          current={progress.current}
          total={progress.total}
          label={progress.label}
        />
      )}

      {partialWarning && (
        <div className="border border-paper bg-surface-raised px-3 py-2 text-center text-sm text-paper">
          {partialWarning}
        </div>
      )}

      {codingSummary && (
        <div className="border border-paper bg-surface-raised px-3 py-2 text-center text-sm text-paper">
          {codingSummary}
        </div>
      )}

      {createdFile && (
        <div>
          <ArtifactCreatedMessage
            name={createdFile.filename}
            viewPath="/coding-view"
            viewState={{ selectedCodedData: createdFile.schema_name }}
          />
        </div>
      )}

      {saveMessage && (
        <div
          className={`border px-3 py-2 text-center text-sm ${
            saveMessageType === "success"
              ? "border-success bg-success/10 text-success"
              : "border-error bg-error/10 text-error"
          }`}
        >
          {saveMessage}
        </div>
      )}
    </div>
  );
}
