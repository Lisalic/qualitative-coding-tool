import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { postFormAndPoll } from "../../api";
import FormShell from "../forms/FormShell";
import DatabaseSourceFields from "../forms/DatabaseSourceFields";
import SliderField from "../forms/SliderField";
import PromptTextareaWithActions from "../forms/PromptTextareaWithActions";
import AiModelFormGroup from "../models/AiModelFormGroup";
import ArtifactCreatedMessage from "../feedback/ArtifactCreatedMessage";
import ProgressBar from "../feedback/ProgressBar";
import ContentScopeFormGroup from "./ContentScopeFormGroup";
import { useToolPanelData } from "./useToolPanelData";
import { useInitialProjectId } from "./useInitialProjectId";
import {
  EXAMPLE_PROMPTS,
  MissingFieldsError,
  buildGenerateCodebookForm,
} from "../../lib/apiContracts";

const EXAMPLE_PROMPT = EXAMPLE_PROMPTS.generate;
const inputClasses =
  "border border-paper bg-white/5 px-3 py-2.5 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";

export default function GenerateCodebookPanel({ prompt, onPromptChange }) {
  const navigate = useNavigate();
  const initialProjectId = useInitialProjectId();
  const [database, setDatabase] = useState("");
  const [databaseType, setDatabaseType] = useState("unfiltered");
  const [selectedProject, setSelectedProject] = useState(initialProjectId);
  const [loading, setLoading] = useState(false);
  const [createdFile, setCreatedFile] = useState(null);
  const [progress, setProgress] = useState(null);
  const [partialWarning, setPartialWarning] = useState("");
  const [error, setError] = useState(null);
  const [description, setDescription] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [saveMessageType, setSaveMessageType] = useState("success");
  const [model, setModel] = useState("");
  const [samplePercentage, setSamplePercentage] = useState(100);
  const [codebookName, setCodebookName] = useState("");
  const [contentScope, setContentScope] = useState("both");
  const {
    databases,
    filteredDatabases,
    projects,
    error: panelDataError,
  } = useToolPanelData();

  const getAvailableDatabases = () => {
    if (databaseType === "filtered") {
      return filteredDatabases;
    }
    return databases;
  };

  const getDisplayName = (item) => {
    if (!item) return "";
    if (typeof item === "string") return item.replace(".db", "");
    if (item.label) return item.label;
    if (item.value) return String(item.value).replace(".db", "");
    return "";
  };

  const getSelectedRecordCount = () => {
    const selected = getAvailableDatabases().find(
      (item) => (item.value || item) === database,
    );
    const tables = selected?.meta?.tables || [];
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
    const selected = getAvailableDatabases().find(
      (item) => (item.value || item) === database,
    );
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
    } else if (postsAvailable && !commentsAvailable && contentScope !== "posts") {
      setContentScope("posts");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [postsAvailable, commentsAvailable]);

  const handleViewCodebook = () => {
    navigate("/codebook-view");
  };

  const handleSubmit = async () => {
    const savedApiKey = localStorage.getItem("apiKey");
    if (!savedApiKey) {
      setError("Please set your API key in the navbar first.");
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setCreatedFile(null);
      setProgress(null);
      setPartialWarning("");

      let requestData;
      try {
        requestData = buildGenerateCodebookForm({
          apiKey: savedApiKey,
          database,
          name: codebookName,
          model,
          prompt,
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

      const { ok, data, error: postError } = await postFormAndPoll(
        "/api/generate-codebook/",
        requestData,
        { onProgress: setProgress },
      );

      if (!ok) {
        setError(postError || "Failed to generate codebook");
        return;
      }
      setCreatedFile(data?.file || null);
      if (data?.partial) {
        const reason = data.partial_error
          ? `Stopped early after an error: ${data.partial_error}`
          : "This is likely due to a free model's batch limit -- use a paid model or reduce the sample size for complete coverage.";
        setPartialWarning(
          `Warning: only ${data.batches_processed}/${data.batches_total} batches completed. ${reason}`,
        );
      }
    } catch (err) {
      if (err.name === "AbortError") {
        setError("Request timed out. Please try again.");
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const handlePromptSaveFeedback = ({ type, message }) => {
    setSaveMessage(message);
    setSaveMessageType(type);
    setTimeout(() => setSaveMessage(""), type === "success" ? 3000 : 4000);
  };

  const databaseOptions = getAvailableDatabases().map((item) => ({
    value: item.value || item,
    label: item.label || getDisplayName(item),
  }));

  const projectOptions = (projects || []).map((p) => ({
    value: String(p.id),
    label: p.projectname,
  }));

  return (
    <div>
      <h1 className="mb-2 text-center text-2xl font-bold">Generate Codebook</h1>

      <div className="mb-6 flex justify-center">
        <button
          type="button"
          onClick={handleViewCodebook}
          className="border border-paper px-4 py-2 text-sm transition-colors hover:bg-paper hover:text-ink"
        >
          View Codebook
        </button>
      </div>

      <FormShell
        onSubmit={handleSubmit}
        submitButton={{
          text: "Generate Codebook",
          loadingText: "Generating...",
          disabled: loading,
        }}
        error={error || panelDataError || null}
      >
        <DatabaseSourceFields
          radioName="generate-database-type"
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
          <label htmlFor="name" className="text-sm">
            Codebook Name
          </label>
          <input
            id="name"
            type="text"
            value={codebookName}
            onChange={(e) => setCodebookName(e.target.value)}
            placeholder="my-codebook"
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
            placeholder="Optional description for the codebook"
            rows={2}
            className={`${inputClasses} resize-y`}
            disabled={loading}
          />
        </div>

        <PromptTextareaWithActions
          id="prompt"
          label="Enter Prompt"
          value={prompt}
          onChange={onPromptChange}
          placeholder="Enter a custom prompt to guide the codebook generation. Leave empty for default behavior."
          rows={2}
          promptType="generate"
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

        <ContentScopeFormGroup
          contentScope={contentScope}
          onContentScopeChange={setContentScope}
          postsAvailable={postsAvailable}
          commentsAvailable={commentsAvailable}
          disabled={loading || !database}
          radioName="generate-content-scope"
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
      </FormShell>

      {loading && progress && (
        <ProgressBar current={progress.current} total={progress.total} label={progress.label} />
      )}

      {partialWarning && (
        <div className="mt-4 border border-paper bg-white/5 px-4 py-3 text-center text-sm text-paper">
          {partialWarning}
        </div>
      )}

      {createdFile && (
        <div className="mt-4">
          <ArtifactCreatedMessage
            name={createdFile.filename}
            viewPath="/codebook-view"
            viewState={{ selected: createdFile.schema_name }}
          />
        </div>
      )}

      {saveMessage && (
        <div
          className={`mt-4 border px-4 py-3 text-center text-sm ${
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
