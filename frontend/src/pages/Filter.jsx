import { useNavigate } from "react-router-dom";
import ActionForm from "../components/ActionForm";
import PromptManager from "../components/PromptManager";
import { useState, useEffect } from "react";
import { apiFetch } from "../api";
import { AI_MODELS } from "../lib/constants";
import "../styles/Home.css";

export default function Filter() {
  const navigate = useNavigate();
  const [filterPrompt, setFilterPrompt] = useState("");
  const [message, setMessage] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [saveMessageType, setSaveMessageType] = useState("success");
  const [loading, setLoading] = useState(false);
  const [database, setDatabase] = useState("");
  const [databases, setDatabases] = useState([]); // raw data projects for selection
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [model, setModel] = useState("");

  const EXAMPLE_PROMPT = `Act as a qualitative research assistant tasked with cleaning raw data transcripts for analysis. For each input item, decide whether it should be kept or removed. Apply these rules: remove spam/automated posts, remove obvious duplicates, and remove non-topical noise. Keep authentic human discussion and on-topic content.`;

  const handleViewFilteredData = () => {
    navigate("/filtered-data");
  };

  const handleLoadPrompt = (prompt) => {
    setFilterPrompt(prompt);
  };

  useEffect(() => {
    fetchDatabases();
  }, []);

  useEffect(() => {
    let mounted = true;
    apiFetch("/api/projects/")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!mounted || !data) return;
        setProjects(data.projects || []);
        if (!selectedProject && data.projects && data.projects.length > 0) {
          setSelectedProject(String(data.projects[0].id));
        }
      })
      .catch(() => {});
    return () => (mounted = false);
  }, []);

  useEffect(() => {
    if (databases.length > 0 && !database) {
      setDatabase(databases[0]);
    }
  }, [databases]);

  const fetchDatabases = async () => {
    try {
      // Fetch raw_data projects for the database select
      const respRaw = await apiFetch("/api/my-files/?file_type=raw_data");
      if (!respRaw.ok) throw new Error("Failed to fetch raw projects");
      const rawData = await respRaw.json();
      const rawOptions = (rawData.projects || []).map((p) => ({
        value: p.schema_name,
        label: p.display_name || p.schema_name,
        meta: p,
      }));

      setDatabases(rawOptions);
      if (!database && rawOptions.length > 0) setDatabase(rawOptions[0].value);
    } catch (err) {
      console.error("Error fetching databases:", err);
    }
  };

  // (filtered databases removed - only unfiltered databases are used in this page)

  const handleFieldChange = (fieldId, value) => {
    if (fieldId === "filterPrompt") {
      setFilterPrompt(value);
    }
    if (fieldId === "database") {
      setDatabase(value);
    }
    if (fieldId === "name") {
      setName(value);
    }
    if (fieldId === "description") {
      setDescription(value);
    }
  };

  const handleSubmit = async (formData) => {
    console.debug(
      "[filter] handleSubmit received formData:",
      formData,
      "component model:",
      model,
    );
    const savedApiKey = localStorage.getItem("apiKey");
    if (!savedApiKey) {
      throw new Error("Please set your API key in the navbar first.");
    }

    if (!formData.filterPrompt.trim()) {
      throw new Error("Please enter a filter prompt");
    }

    // Require a name for the filtered DB
    if (!formData.name || !formData.name.trim()) {
      throw new Error("Please provide a name for the filtered database");
    }

    setLoading(true);
    setMessage("");

    try {
      const requestData = new FormData();
      requestData.append("api_key", savedApiKey);
      requestData.append("prompt", formData.filterPrompt);
      // Only use the model explicitly provided by the user via the form
      const modelToSend = formData.model;
      if (modelToSend) requestData.append("model", modelToSend);
      // include desired output name if provided
      if (formData.name) {
        requestData.append("name", formData.name);
      }
      if (formData.description) {
        requestData.append("description", formData.description);
      }
      // include selected database if provided
      if (formData.database) {
        requestData.append("database", formData.database);
      }
      if (selectedProject) {
        requestData.append("project_id", selectedProject);
      }

      const response = await apiFetch("/api/filter-data/", {
        method: "POST",
        body: requestData,
      });

      if (!response.ok) {
        const text = await response.text();
        let errorMsg = "Filtering failed";
        try {
          const errorData = JSON.parse(text);
          errorMsg = errorData.detail || errorMsg;
        } catch (e) {
          errorMsg = text || errorMsg;
        }
        throw new Error(errorMsg);
      }

      const text = await response.text();
      const data = JSON.parse(text);

      setMessage(`✓ ${data.message}`);
      setFilterPrompt("");
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fields = [
    {
      id: "filterPrompt",
      label: "Enter prompt",
      type: "textarea",
      value: filterPrompt,
      onChange: (v) => setFilterPrompt(v),
      placeholder: "Enter your filter prompt...",
      rows: 5,
      extraButtons: [
        {
          label: "Save prompt",
          onClick: async () => {
            try {
              const { api } = await import("../api");

              if (!filterPrompt || !filterPrompt.trim()) {
                alert("Please enter a prompt before saving");
                return;
              }

              // Match PromptManager behavior: attempt to fetch /api/me (non-fatal), then post FormData
              let fetchedUserId = null;
              try {
                const me = await api.get("/api/me");
                fetchedUserId = me?.data?.id || me?.data?.sub || null;
              } catch (e) {
                console.warn("Could not fetch /api/me", e);
              }

              let promptName = `Prompt ${Date.now()}`;
              try {
                const listRes = await api.get(
                  `/api/prompts/?prompt_type=${encodeURIComponent("filter")}`,
                );
                const prompts = (listRes.data && listRes.data.prompts) || [];
                promptName = `Prompt ${prompts.length + 1}`;
              } catch (e) {
                // fallback to timestamp-based name
              }
              const form = new FormData();
              form.append("promptname", promptName);
              form.append("prompt", filterPrompt.trim());
              form.append("type", "filter");
              if (fetchedUserId) form.append("user_id", fetchedUserId);

              const res = await api.post("/api/prompts/", form);
              console.log("Saved prompt response:", res);
              const saved = res && res.data ? res.data : null;
              const label =
                (saved &&
                  (saved.promptname || saved.display_name || saved.prompt)) ||
                "Prompt saved";
              setSaveMessage(`Saved: ${label}`);
              setSaveMessageType("success");
              // ensure the right-hand manager switches to prompts and reloads
              try {
                window.dispatchEvent(new Event("promptSaved"));
              } catch (e) {}
              setTimeout(() => setSaveMessage(""), 3000);
            } catch (err) {
              console.error("Failed to save prompt:", err);
              const msg =
                err?.response?.data?.detail ||
                err?.message ||
                "Failed to save prompt";
              setSaveMessage(String(msg));
              setSaveMessageType("error");
              setTimeout(() => setSaveMessage(""), 4000);
            }
          },
          className: "load-prompt-btn",
        },
        {
          label: "Load example prompt",
          onClick: () => setFilterPrompt(EXAMPLE_PROMPT),
          className: "load-prompt-btn",
        },
      ],
    },
    {
      id: "model",
      label: "AI Model",
      type: "select",
      value: model,
      onChange: (v) => setModel(v),
      options: AI_MODELS,
    },
  ];

  const nameField = {
    id: "name",
    label: "Filtered Database Name",
    type: "text",
    value: name,
    placeholder: "my-filtered-db",
  };

  const descriptionField = {
    id: "description",
    label: "Description (optional)",
    type: "textarea",
    value: description,
    placeholder: "Optional description for the filtered database",
    rows: 3,
    onChange: (v) => setDescription(v),
  };

  const databaseFields = [
    {
      id: "database",
      label: "Select Database",
      type: "select",
      value: database,
      options: databases.map((d) => ({
        value: d.value,
        label: d.label,
      })),
    },
    {
      id: "project_id",
      label: "Select Project",
      type: "select",
      value: selectedProject,
      onChange: (v) => setSelectedProject(v),
      options: projects.map((p) => ({
        value: String(p.id),
        label: p.projectname,
      })),
    },
  ];

  return (
    <>
      <div className="home-container">
        <div className="tool-page-layout">
          <div className="left-section">
            <div className="file-upload">
              <h1
                style={{
                  textAlign: "center",
                  fontSize: "28px",
                  fontWeight: "600",
                  margin: "0 0 10px 0",
                }}
              >
                Apply Filter
              </h1>
              <div className="action-buttons">
                <button
                  onClick={handleViewFilteredData}
                  className="view-button"
                >
                  View Filtered Data
                </button>
              </div>
              {/* project select moved into ActionForm fields */}
              <ActionForm
                fields={[
                  ...databaseFields,
                  nameField,
                  descriptionField,
                  ...fields,
                ]}
                submitButton={{
                  text: "Filter",
                  loadingText: "Processing...",
                  disabled: loading,
                }}
                onSubmit={handleSubmit}
                error={message && message.startsWith("Error:") ? message : null}
                result={message && message.startsWith("✓") ? message : null}
                resultTitle="Filter Result"
              />
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
          </div>
          <div className="prompt-manager-section">
            <PromptManager
              onLoadPrompt={handleLoadPrompt}
              currentPrompt={filterPrompt}
              promptType="filter"
            />
          </div>
        </div>
      </div>
    </>
  );
}
