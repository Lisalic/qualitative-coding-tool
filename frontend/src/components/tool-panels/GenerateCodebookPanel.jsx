import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../../api";
import FormShell from "../forms/FormShell";
import DatabaseSourceFields from "../forms/DatabaseSourceFields";
import SamplePercentageSlider from "../forms/SamplePercentageSlider";
import PromptTextareaWithActions from "../forms/PromptTextareaWithActions";
import { AI_MODELS } from "../../lib/constants";
import "../../styles/Home.css";
import "../../styles/Data.css";

const EXAMPLE_PROMPT = `You are a codebook generator. Read representative dataset excerpts and propose a concise codebook of [topic]. Keep entries concise and focused; do not add unrelated commentary.
Research Context: These are excerpts from [e.g., reddit stories about bullying]. Specific Focus: Please generate codes specifically related to [e.g., retrospective bullying experiences.]`;

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

      const requestData = new FormData();
      requestData.append("api_key", savedApiKey);
      requestData.append("database", database);
      if (prompt) requestData.append("prompt", prompt);
      if (model) requestData.append("model", model);
      requestData.append(
        "sample_percentage",
        String(
          Number.isFinite(Number(samplePercentage))
            ? Number(samplePercentage)
            : 100,
        ),
      );

      if (selectedProject) {
        requestData.append("project_id", selectedProject);
      }

      if (!codebookName || !codebookName.trim()) {
        throw new Error("Please provide a name for the generated codebook");
      }
      requestData.append("name", codebookName.trim());
      if (description) requestData.append("description", description);

      const response = await apiFetch("/api/generate-codebook/", {
        method: "POST",
        body: requestData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      if (data.error) {
        setError(data.error);
      } else {
        setResult(data.codebook);
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
    <div className="file-upload">
      <h1
        style={{
          textAlign: "center",
          fontSize: "28px",
          fontWeight: "600",
          margin: "0 0 10px 0",
        }}
      >
        Generate Codebook
      </h1>

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
          rows={4}
          promptType="generate"
          exampleText={EXAMPLE_PROMPT}
          disabled={loading}
          onSaveFeedback={handlePromptSaveFeedback}
        />

        <div className="form-group">
          <label htmlFor="model">AI Model</label>
          <select
            id="model"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="form-input"
            disabled={loading}
          >
            {[{ value: "", label: "-- select model --" }, ...AI_MODELS].map(
              (opt) => (
                <option key={opt.value || "empty"} value={opt.value}>
                  {opt.label}
                </option>
              ),
            )}
          </select>
        </div>

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
