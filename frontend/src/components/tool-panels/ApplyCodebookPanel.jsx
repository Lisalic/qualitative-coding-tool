import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { postForm } from "../../api";
import FormShell from "../forms/FormShell";
import DatabaseSourceFields from "../forms/DatabaseSourceFields";
import SamplePercentageSlider from "../forms/SamplePercentageSlider";
import PromptTextareaWithActions from "../forms/PromptTextareaWithActions";
import AiModelFormGroup from "../models/AiModelFormGroup";
import { useToolPanelData } from "./useToolPanelData";
import {
  EXAMPLE_PROMPTS,
  MissingFieldsError,
  buildApplyCodebookForm,
} from "../../lib/apiContracts";
import "../../styles/Home.css";

const EXAMPLE_PROMPT = EXAMPLE_PROMPTS.apply;

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
  const [selectedProject, setSelectedProject] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [saveMessageType, setSaveMessageType] = useState("success");
  const [model, setModel] = useState("");
  const [samplePercentage, setSamplePercentage] = useState(100);
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

  const handleViewCoding = () => {
    navigate("/coding-view");
  };

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
      setResult(null);

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
        });
      } catch (err) {
        if (err instanceof MissingFieldsError) {
          setError(err.message);
          return;
        }
        throw err;
      }

      const { ok, data, error: postError } = await postForm(
        "/api/apply-codebook/",
        requestData,
      );

      if (!ok) {
        setError(postError || "Failed to apply codebook");
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

  const displayError = error || panelDataError || (result && result.error);
  const displayResult = result && result.classification_report;

  return (
    <div className="file-upload">
      <h1 className="tool-page-title">Apply Codebook</h1>

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
