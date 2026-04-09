import { useNavigate } from "react-router-dom";
import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "../../api";
import FormShell from "../forms/FormShell";
import DatabaseSourceFields from "../forms/DatabaseSourceFields";
import PromptTextareaWithActions from "../forms/PromptTextareaWithActions";
import MinWordsField from "../forms/MinWordsField";
import SamplePercentageSlider from "../forms/SamplePercentageSlider";
import { AI_MODELS } from "../../lib/constants";
import "../../styles/Home.css";

const EXAMPLE_PROMPT = `Act as a qualitative research assistant tasked with cleaning raw data transcripts for analysis. For each input item, decide whether it should be kept or removed. Apply these rules: remove spam/automated posts, remove obvious duplicates, and remove non-topical noise. Keep authentic human discussion and on-topic content.`;

export default function FilterDataPanel({
  filterPrompt,
  onFilterPromptChange,
}) {
  const navigate = useNavigate();
  const [message, setMessage] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [saveMessageType, setSaveMessageType] = useState("success");
  const [loading, setLoading] = useState(false);
  const [database, setDatabase] = useState("");
  const [databaseType, setDatabaseType] = useState("unfiltered");
  const [databases, setDatabases] = useState([]);
  const [filteredDatabases, setFilteredDatabases] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [model, setModel] = useState("");
  const [minWords, setMinWords] = useState(0);
  const [samplePercentage, setSamplePercentage] = useState(100);
  const [filterTags, setFilterTags] = useState("");
  const [wordCountRanges, setWordCountRanges] = useState({
    submissions: [],
    comments: [],
  });
  const [rangesLoading, setRangesLoading] = useState(false);

  useEffect(() => {
    fetchDatabases();
    fetchFilteredDatabases();
  }, []);

  useEffect(() => {
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

  const fetchWordCountRanges = useCallback(async (schema) => {
    if (!schema) {
      setWordCountRanges({ submissions: [], comments: [] });
      setRangesLoading(false);
      return;
    }
    const schemaVal = typeof schema === "object" ? schema.value : schema;
    if (!schemaVal) {
      setWordCountRanges({ submissions: [], comments: [] });
      setRangesLoading(false);
      return;
    }
    setRangesLoading(true);
    setWordCountRanges({ submissions: [], comments: [] });
    try {
      const resp = await apiFetch(
        `/api/word-count-ranges/?schema=${encodeURIComponent(schemaVal)}`,
      );
      if (resp.ok) {
        const data = await resp.json();
        setWordCountRanges({
          submissions: data.submissions || [],
          comments: data.comments || [],
        });
      } else {
        setWordCountRanges({ submissions: [], comments: [] });
      }
    } catch (e) {
      console.error("Error fetching word count ranges:", e);
      setWordCountRanges({ submissions: [], comments: [] });
    } finally {
      setRangesLoading(false);
    }
  }, []);

  const getCurrentCounts = useCallback(() => {
    const submissions = wordCountRanges.submissions
      .filter((range) => range.min_words >= minWords)
      .reduce((sum, range) => sum + range.count, 0);

    const comments = wordCountRanges.comments
      .filter((range) => range.min_words >= minWords)
      .reduce((sum, range) => sum + range.count, 0);

    return { submissions, comments };
  }, [wordCountRanges, minWords]);

  useEffect(() => {
    fetchWordCountRanges(database);
  }, [database, fetchWordCountRanges]);

  const fetchDatabases = async () => {
    try {
      const respRaw = await apiFetch("/api/my-files/?file_type=raw_data");
      if (!respRaw.ok) throw new Error("Failed to fetch raw projects");
      const rawData = await respRaw.json();
      const rawOptions = (rawData.projects || []).map((p) => ({
        value: p.schema_name,
        label: p.display_name || p.schema_name,
        meta: p,
      }));

      setDatabases(rawOptions);
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

  const handleDatabaseTypeChange = (type) => {
    setDatabaseType(type);
    setDatabase("");
  };

  const validateForm = () => {
    const missing = [];
    if (!database) missing.push("Database");
    if (!selectedProject) missing.push("Project");
    if (!name || !name.trim()) {
      missing.push("Filtered Database Name");
    }
    if (!model || !model.trim()) {
      missing.push("AI Model");
    }
    if (missing.length) {
      return `Missing required fields: ${missing.join(", ")}`;
    }
    const savedApiKey = localStorage.getItem("apiKey");
    if (!savedApiKey) {
      return "API key not set. Please set your API key in the navbar.";
    }
    return null;
  };

  const buildRequestData = (apiKey) => {
    const requestData = new FormData();
    requestData.append("api_key", apiKey);
    if (filterPrompt) {
      requestData.append("prompt", filterPrompt);
    }
    if (filterTags && filterTags.trim()) {
      requestData.append("filter_tags", filterTags.trim());
    }
    if (model) {
      requestData.append("model", model);
    }
    if (name) {
      requestData.append("name", name);
    }
    if (description) {
      requestData.append("description", description);
    }
    if (database) {
      requestData.append("database", database);
    }
    if (selectedProject) {
      requestData.append("project_id", selectedProject);
    }
    if (minWords > 0) {
      requestData.append("min_words", String(minWords));
    }
    requestData.append(
      "sample_percentage",
      String(
        Number.isFinite(Number(samplePercentage))
          ? Number(samplePercentage)
          : 100,
      ),
    );
    return requestData;
  };

  const parseErrorResponse = async (response) => {
    const text = await response.text();
    let errorMsg = `Filtering failed (HTTP ${response.status})`;
    if (!text) return errorMsg;
    try {
      const errorData = JSON.parse(text);
      if (typeof errorData.error === "string") return errorData.error;
      if (typeof errorData.detail === "string") return errorData.detail;
      return errorMsg;
    } catch {
      return text || errorMsg;
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    setMessage("");

    try {
      const validationError = validateForm();
      if (validationError) {
        setMessage(`Error: ${validationError}`);
        return;
      }

      const savedApiKey = localStorage.getItem("apiKey");
      const requestData = buildRequestData(savedApiKey);

      const response = await apiFetch("/api/filter-data/", {
        method: "POST",
        body: requestData,
      });

      if (!response.ok) {
        const errorMsg = await parseErrorResponse(response);
        setMessage(`Error: ${errorMsg}`);
        return;
      }

      const text = await response.text();
      const data = JSON.parse(text);

      let resultMessage = `✓ ${data.message}`;
      if (data.tag_filter) {
        resultMessage += `\n\nTag expansion:\n${JSON.stringify(
          data.tag_filter,
          null,
          2,
        )}`;
      }
      if (data.ai_response) {
        resultMessage += `\n\nAI Response:\n${JSON.stringify(
          data.ai_response,
          null,
          2,
        )}`;
      }
      setMessage(resultMessage);
      onFilterPromptChange("");
      setFilterTags("");
    } catch (err) {
      setMessage(`Error: ${err.message || "Filtering failed"}`);
    } finally {
      setLoading(false);
    }
  };

  const handleViewFilteredData = () => {
    navigate("/filtered-data");
  };

  const handlePromptSaveFeedback = ({ type, message }) => {
    setSaveMessage(message);
    setSaveMessageType(type);
    setTimeout(() => setSaveMessage(""), type === "success" ? 3000 : 4000);
  };

  const counts = getCurrentCounts();
  const minWordsCaption = `${counts.submissions + counts.comments} records match (${counts.submissions} submissions, ${counts.comments} comments)`;

  const databaseOptions = getAvailableDatabases().map((item) => ({
    value: item.value || item,
    label: item.label || String(item.value || item),
  }));

  const projectOptions = (projects || []).map((p) => ({
    value: String(p.id),
    label: p.projectname,
  }));

  return (
    <div className="file-upload">
      <h1 className="tool-page-title">Apply Filter</h1>
      <div className="action-buttons">
        <button
          type="button"
          onClick={handleViewFilteredData}
          className="view-button"
        >
          View Filtered Data
        </button>
      </div>

      <FormShell
        onSubmit={handleSubmit}
        submitButton={{
          text: "Filter",
          loadingText: "Processing...",
          disabled: loading,
        }}
        error={message && message.startsWith("Error:") ? message : null}
        result={message && message.startsWith("✓") ? message : null}
        resultTitle="Filter Result"
      >
        <DatabaseSourceFields
          radioName="filter-database-type"
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
          <label htmlFor="name">Filtered Database Name</label>
          <input
            id="name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="my-filtered-db"
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
            placeholder="Optional description for the filtered database"
            rows={3}
            className="form-input"
            disabled={loading}
          />
        </div>

        <PromptTextareaWithActions
          id="filterPrompt"
          label="Enter prompt"
          value={filterPrompt}
          onChange={onFilterPromptChange}
          placeholder="Enter your filter prompt..."
          rows={5}
          promptType="filter"
          exampleText={EXAMPLE_PROMPT}
          disabled={loading}
          onSaveFeedback={handlePromptSaveFeedback}
        />

        <div className="form-group">
          <label htmlFor="filterTags">Tags (optional)</label>
          <textarea
            id="filterTags"
            value={filterTags}
            onChange={(e) => setFilterTags(e.target.value)}
            placeholder="Comma-separated keywords (optional)."
            rows={3}
            className="form-input"
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="model">AI Model</label>
          <select
            id="model"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="form-input"
            disabled={loading}
          >
            {!model && (
              <option value="" disabled>
                Select an AI model
              </option>
            )}
            {AI_MODELS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <MinWordsField
          value={minWords}
          onChange={setMinWords}
          disabled={loading}
          rangesLoading={rangesLoading}
          caption={minWordsCaption}
        />

        <SamplePercentageSlider
          value={samplePercentage}
          onChange={setSamplePercentage}
          disabled={loading}
          databaseSelected={Boolean(database)}
          totalCount={counts.submissions + counts.comments}
        />
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
