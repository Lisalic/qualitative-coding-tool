import { useNavigate } from "react-router-dom";
import { useState, useEffect, useCallback } from "react";
import { apiFetch, postFormAndPoll } from "../../api";
import FormShell from "../forms/FormShell";
import DatabaseSourceFields from "../forms/DatabaseSourceFields";
import PromptTextareaWithActions from "../forms/PromptTextareaWithActions";
import AiLabel from "../forms/AiLabel";
import SliderField from "../forms/SliderField";
import AiModelFormGroup from "../models/AiModelFormGroup";
import { useToolPanelData } from "./useToolPanelData";
import {
  EXAMPLE_PROMPTS,
  MissingFieldsError,
  buildFilterDataForm,
} from "../../lib/apiContracts";

const EXAMPLE_PROMPT = EXAMPLE_PROMPTS.filter;
const inputClasses =
  "border border-paper bg-white/5 px-3 py-2.5 text-paper placeholder:text-paper/40 focus:outline-none focus:ring-2 focus:ring-paper disabled:opacity-50";

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
  const {
    databases,
    filteredDatabases,
    projects,
    error: panelDataError,
  } = useToolPanelData();

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

  const handleSubmit = async () => {
    setLoading(true);
    setMessage("");

    try {
      const savedApiKey = localStorage.getItem("apiKey");
      if (!savedApiKey) {
        setMessage(
          "Error: API key not set. Please set your API key in the navbar.",
        );
        return;
      }

      let requestData;
      try {
        requestData = buildFilterDataForm({
          apiKey: savedApiKey,
          database,
          name,
          model,
          projectId: selectedProject || null,
          prompt: filterPrompt,
          description,
          minWords,
          samplePercentage,
          filterTags,
        });
      } catch (err) {
        if (err instanceof MissingFieldsError) {
          setMessage(`Error: ${err.message}`);
          return;
        }
        throw err;
      }

      const { ok, data, error } = await postFormAndPoll(
        "/api/filter-data/",
        requestData,
      );

      if (!ok) {
        setMessage(`Error: ${error || "Filtering failed"}`);
        return;
      }

      let resultMessage = `✓ ${data?.message || "Database filtered and saved"}`;
      if (data?.tag_filter) {
        resultMessage += `\n\nTag expansion:\n${JSON.stringify(
          data.tag_filter,
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
    <div>
      <h1 className="mb-2 text-center text-2xl font-bold">Apply Filter</h1>
      <div className="mb-6 flex justify-center">
        <button
          type="button"
          onClick={handleViewFilteredData}
          className="border border-paper px-4 py-2 text-sm transition-colors hover:bg-paper hover:text-ink"
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
        error={
          message && message.startsWith("Error:")
            ? message
            : panelDataError || null
        }
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

        <div className="flex flex-col gap-1.5">
          <label htmlFor="name" className="text-sm">
            Filtered Database Name
          </label>
          <input
            id="name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="my-filtered-db"
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
            placeholder="Optional description for the filtered database"
            rows={3}
            className={`${inputClasses} resize-y`}
            disabled={loading}
          />
        </div>

        <PromptTextareaWithActions
          id="filterPrompt"
          label="Enter prompt"
          value={filterPrompt}
          onChange={onFilterPromptChange}
          placeholder="Enter your filter prompt..."
          rows={3}
          promptType="filter"
          exampleText={EXAMPLE_PROMPT}
          disabled={loading}
          onSaveFeedback={handlePromptSaveFeedback}
        />

        <div className="flex flex-col gap-1.5">
          <AiLabel htmlFor="filterTags" text="Keywords (optional)" />
          <textarea
            id="filterTags"
            value={filterTags}
            onChange={(e) => setFilterTags(e.target.value)}
            placeholder="Comma-separated keywords (optional)."
            rows={3}
            className={`${inputClasses} resize-y`}
            disabled={loading}
          />
        </div>

        <AiModelFormGroup
          model={model}
          onModelChange={setModel}
          disabled={loading}
          selectPlaceholder="filter"
        />

        <SliderField
          id="minWords"
          label="Minimum Words"
          value={minWords}
          onChange={setMinWords}
          min={0}
          max={1000}
          step={10}
          disabled={loading}
          valueDisplay={minWords}
          valueMinWidth="60px"
          caption={rangesLoading ? "Loading word count ranges..." : minWordsCaption}
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
              : `${Math.ceil(
                  ((counts.submissions + counts.comments) * samplePercentage) / 100,
                )} of ${counts.submissions + counts.comments} records will be selected randomly.`
          }
        />
      </FormShell>

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
