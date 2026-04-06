import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch } from "../../api";
import FormShell from "../forms/FormShell";
import DatabaseSourceFields from "../forms/DatabaseSourceFields";
import SamplePercentageSlider from "../forms/SamplePercentageSlider";
import PromptTextareaWithActions from "../forms/PromptTextareaWithActions";
import { AI_MODELS } from "../../lib/constants";
import "../../styles/Home.css";

const EXAMPLE_PROMPT = `You are a coding assistant. Given a codebook and an input item, decide which code(s) from the codebook apply and provide a one-sentence justification. Focus on selecting the single best code when applicable; do not invent new codes. Keep responses concise.`;

export default function ApplyCodebookPanel({ methodology, onMethodologyChange }) {
  const navigate = useNavigate();
  const [database, setDatabase] = useState("");
  const [reportName, setReportName] = useState("");
  const [databaseType, setDatabaseType] = useState("unfiltered");
  const [codebook, setCodebook] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [description, setDescription] = useState("");
  const [codebooks, setCodebooks] = useState([]);
  const [databases, setDatabases] = useState([]);
  const [filteredDatabases, setFilteredDatabases] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [saveMessageType, setSaveMessageType] = useState("success");
  const [model, setModel] = useState("");
  const [samplePercentage, setSamplePercentage] = useState(100);

  useEffect(() => {
    fetchCodebooks();
    fetchDatabases();
    fetchFilteredDatabases();
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const resp = await apiFetch("/api/projects/");
      if (!resp.ok) return;
      const data = await resp.json();
      setProjects(data.projects || []);
    } catch (err) {
      console.error("Error fetching projects:", err);
    }
  };

  const fetchCodebooks = async () => {
    try {
      const response = await apiFetch("/api/list-codebooks");
      if (!response.ok) throw new Error("Failed to fetch codebooks");
      const data = await response.json();
      setCodebooks(data.codebooks);
      setCodebook((prev) => {
        if (prev) return prev;
        if (data.codebooks.length > 0) {
          return data.codebooks[0].id.toString();
        }
        return prev;
      });
    } catch (err) {
      console.error("Error fetching codebooks:", err);
    }
  };

  const fetchDatabases = async () => {
    try {
      const projResp = await apiFetch("/api/my-files/?file_type=raw_data");
      if (projResp.ok) {
        const projData = await projResp.json();
        const projectsList = projData.projects || [];
        const normalized = projectsList.map((p) => ({
          name: p.schema_name,
          display_name: p.display_name,
          metadata: p,
        }));
        setDatabases(normalized);
        return;
      }

      const response = await apiFetch("/api/my-files/?file_type=raw_data");
      if (!response.ok) throw new Error("Failed to fetch projects");
      const data = await response.json();
      const normalized = (data.projects || []).map((p) => ({
        name: p.schema_name,
        display_name: p.display_name,
        metadata: p,
      }));
      setDatabases(normalized);
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
        const normalized = projectsList.map((p) => ({
          name: p.schema_name,
          display_name: p.display_name,
          metadata: p,
        }));
        setFilteredDatabases(normalized);
        return;
      }

      setFilteredDatabases([]);
    } catch (err) {
      console.error("Error fetching filtered databases:", err);
    }
  };

  const handleViewCoding = () => {
    navigate("/coding-view");
  };

  const parseApplyCodebookError = async (response) => {
    try {
      const payload = await response.json();
      if (payload?.error) return String(payload.error);
      if (payload?.detail) {
        return typeof payload.detail === "string"
          ? payload.detail
          : JSON.stringify(payload.detail);
      }
      return JSON.stringify(payload);
    } catch {
      try {
        const textPayload = await response.text();
        if (textPayload) return textPayload;
      } catch {
        /* ignore */
      }
      return `HTTP error! status: ${response.status}`;
    }
  };

  const handleSubmit = async () => {
    const savedApiKey = localStorage.getItem("apiKey");
    if (!savedApiKey) {
      setError("Please set your API key in the navbar first.");
      return;
    }
    if (!reportName || !reportName.trim()) {
      setError(
        "Please provide an output display name (report name) before applying the codebook.",
      );
      return;
    }
    if (!codebook || !codebook.trim()) {
      setError("Please select a codebook before applying.");
      return;
    }
    if (codebooks.length === 0) {
      setError("No codebooks available. Please create a codebook first.");
      return;
    }
    if (!database || !database.trim()) {
      setError("Please select a database before applying.");
      return;
    }
    try {
      setLoading(true);
      setError(null);
      setResult(null);

      const requestData = new FormData();
      requestData.append("api_key", savedApiKey);
      requestData.append("database", database);
      requestData.append("report_name", reportName);
      requestData.append("codebook", codebook);
      requestData.append("methodology", methodology);
      if (model) requestData.append("model", model);
      requestData.append(
        "sample_percentage",
        String(
          Number.isFinite(Number(samplePercentage))
            ? Number(samplePercentage)
            : 100,
        ),
      );
      if (description) requestData.append("description", description);
      if (selectedProject) {
        requestData.append("project_id", selectedProject);
      }

      const response = await apiFetch("/api/apply-codebook/", {
        method: "POST",
        body: requestData,
      });

      if (!response.ok) {
        const errorMsg = await parseApplyCodebookError(response);
        throw new Error(errorMsg || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      if (data?.error) {
        setError(String(data.error));
        return;
      }
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
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

  const handleDatabaseTypeChange = (type) => {
    setDatabaseType(type);
    setDatabase("");
  };

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

  const displayError = error || (result && result.error);
  const displayResult = result && result.classification_report;

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
        Apply Codebook
      </h1>

      <div className="action-buttons">
        <button type="button" onClick={handleViewCoding} className="view-button">
          View Coding Results
        </button>
      </div>

      <FormShell
        onSubmit={handleSubmit}
        submitButton={{
          text: "Apply Codebook",
          loadingText: "Applying...",
          disabled: loading,
        }}
        error={displayError}
        result={displayResult}
        resultTitle="Classification Report"
      >
        <DatabaseSourceFields
          radioName="apply-database-type"
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

        <div className="form-group">
          <label htmlFor="codebook">Select Codebook</label>
          <select
            id="codebook"
            value={codebook}
            onChange={(e) => setCodebook(e.target.value)}
            className="form-input"
            disabled={loading}
          >
            {codebooks.length === 0 ? (
              <option value="">No codebooks available</option>
            ) : (
              codebooks.map((cb) => (
                <option key={cb.id} value={cb.id.toString()}>
                  {cb.name || cb.display_name || cb.id.toString()}
                </option>
              ))
            )}
          </select>
        </div>

        <PromptTextareaWithActions
          id="methodology"
          label="Enter Prompt"
          value={methodology}
          onChange={onMethodologyChange}
          placeholder="Enter your coding methodology or leave blank..."
          rows={4}
          promptType="apply"
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
          <label htmlFor="report_name">Report Name</label>
          <input
            id="report_name"
            type="text"
            value={reportName}
            onChange={(e) => setReportName(e.target.value)}
            placeholder="Enter report name... "
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
            placeholder="Optional description for the report"
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
