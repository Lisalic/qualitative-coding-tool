import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch, postForm } from "../../api";
import FormShell from "../forms/FormShell";
import DatabaseSourceFields from "../forms/DatabaseSourceFields";
import SamplePercentageSlider from "../forms/SamplePercentageSlider";
import PromptTextareaWithActions from "../forms/PromptTextareaWithActions";
import AiModelFormGroup from "../AiModelFormGroup";
import {
  EXAMPLE_PROMPTS,
  MissingFieldsError,
  buildGenerateCodebookForm,
} from "../../lib/apiContracts";
import "../../styles/Home.css";

const EXAMPLE_PROMPT = EXAMPLE_PROMPTS.generate;

export default function GenerateCodebookPanel({ prompt, onPromptChange }) {
  const navigate = useNavigate();
  const [database, setDatabase] = useState("");
  const [databaseType, setDatabaseType] = useState("unfiltered");
  const [databases, setDatabases] = useState([]);
  const [filteredDatabases, setFilteredDatabases] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [description, setDescription] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [saveMessageType, setSaveMessageType] = useState("success");
  const [model, setModel] = useState("");
  const [samplePercentage, setSamplePercentage] = useState(100);
  const [codebookName, setCodebookName] = useState("");

  useEffect(() => {
    fetchDatabases();
    fetchFilteredDatabases();
    let mounted = true;
    apiFetch("/api/projects/")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!mounted || !data) return;
        setProjects(data.projects || []);
      })
      .catch(() => {});
    return () => (mounted = false);
  }, []);

  const fetchDatabases = async () => {
    try {
      const response = await apiFetch("/api/my-files/?file_type=raw_data");
      if (!response.ok) throw new Error("Failed to fetch projects");
      const data = await response.json();

      const projectOptions = (data.projects || []).map((p) => ({
        value: p.schema_name,
        label: p.display_name || p.schema_name,
        meta: p,
      }));

      setDatabases(projectOptions);
    } catch (err) {
      console.error("Error fetching databases:", err);
    }
  };

  const fetchFilteredDatabases = async () => {
    try {
      const projResp = await apiFetch("/api/my-files/?file_type=filtered_data");
      if (projResp.ok) {
        const projData = await projResp.json();
        const projectsList = projData.projects || [];
        const projectOptions = projectsList.map((p) => ({
          value: p.schema_name,
          label: p.display_name || p.schema_name,
          meta: p,
        }));
        setFilteredDatabases(projectOptions);
        return;
      }

      setFilteredDatabases([]);
    } catch (err) {
      console.error("Error fetching filtered databases:", err);
    }
  };

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

  const handleDatabaseTypeChange = (type) => {
    setDatabaseType(type);
    setDatabase("");
  };

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
      setResult(null);

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
        });
      } catch (err) {
        if (err instanceof MissingFieldsError) {
          setError(err.message);
          return;
        }
        throw err;
      }

      const { ok, data, error: postError } = await postForm(
        "/api/generate-codebook/",
        requestData,
      );

      if (!ok) {
        setError(postError || "Failed to generate codebook");
        return;
      }
      setResult(data?.codebook ?? "");
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
    <div className="file-upload">
      <h1 className="tool-page-title">Generate Codebook</h1>

      <div className="action-buttons">
        <button type="button" onClick={handleViewCodebook} className="view-button">
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
        error={error}
        result={result}
        resultTitle="Generated Codebook"
      >
        <DatabaseSourceFields
          radioName="generate-database-type"
          databaseType={databaseType}
          onDatabaseTypeChange={handleDatabaseTypeChange}
          database={database}
          onDatabaseChange={setDatabase}
          databaseOptions={databaseOptions}
          databasePlaceholder="Select a database"
          selectedProject={selectedProject}
          onProjectChange={setSelectedProject}
          projectOptions={projectOptions}
          disabled={loading}
        />

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

        <SamplePercentageSlider
          value={samplePercentage}
          onChange={setSamplePercentage}
          disabled={loading}
          databaseSelected={Boolean(database)}
          totalCount={getSelectedRecordCount()}
        />

        <div className="form-group">
          <label htmlFor="name">Codebook Name</label>
          <input
            id="name"
            type="text"
            value={codebookName}
            onChange={(e) => setCodebookName(e.target.value)}
            placeholder="my-codebook"
            className="form-input"
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="description">Description (optional)</label>
          <textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Optional description for the codebook"
            rows={2}
            className="form-input"
            disabled={loading}
          />
        </div>
      </FormShell>

      {saveMessage && (
        <div
          className={
            saveMessageType === "success"
              ? "success-message"
              : "error-message"
          }
        >
          {saveMessage}
        </div>
      )}
    </div>
  );
}
