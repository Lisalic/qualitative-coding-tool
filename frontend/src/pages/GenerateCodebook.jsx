import { useState, useEffect } from "react";
import { apiFetch } from "../api";
import { useNavigate } from "react-router-dom";
import ActionForm from "../components/ActionForm";
import CodebookManager from "../components/CodebookManager";
import PromptManager from "../components/PromptManager";
import "../styles/Home.css";
import "../styles/Data.css";

export default function GenerateCodebook() {
  const navigate = useNavigate();
  const EXAMPLE_PROMPT = `You are a codebook generator. Read representative dataset excerpts and propose a concise codebook of [topic]. Keep entries concise and focused; do not add unrelated commentary.
Research Context: These are excerpts from [e.g., reddit stories about bullying]. Specific Focus: Please generate codes specifically related to [e.g., retrospective bullying experiences.]`;
  const [prompt, setPrompt] = useState("");
  const [database, setDatabase] = useState("");
  const [databaseType, setDatabaseType] = useState("unfiltered");
  const [databases, setDatabases] = useState([]);
  const [filteredDatabases, setFilteredDatabases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [description, setDescription] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const [saveMessageType, setSaveMessageType] = useState("success");
  const [rightView, setRightView] = useState("codebooks"); // 'codebooks' or 'prompts'

  useEffect(() => {
    fetchDatabases();
    fetchFilteredDatabases();
  }, []);

  const fetchDatabases = async () => {
    try {
      // Prefer Postgres projects; list-databases removed in favor of my-projects
      const response = await apiFetch("/api/my-files/?file_type=raw_data");
      if (!response.ok) throw new Error("Failed to fetch projects");
      const data = await response.json();

      const projectOptions = (data.projects || []).map((p) => ({
        value: p.schema_name,
        label: p.display_name || p.schema_name,
        meta: p,
      }));

      const combined = [...projectOptions];
      setDatabases(combined);
      // Set default database if none selected
      if (!database && combined.length > 0) {
        setDatabase(combined[0].value);
      }
    } catch (err) {
      console.error("Error fetching databases:", err);
    }
  };

  const fetchFilteredDatabases = async () => {
    try {
      const projResp = await apiFetch("/api/my-files/?file_type=filtered_data");
      if (projResp.ok) {
        const projData = await projResp.json();
        const projects = projData.projects || [];
        const projectOptions = projects.map((p) => ({
          value: p.schema_name,
          label: p.display_name || p.schema_name,
          meta: p,
        }));
        setFilteredDatabases(projectOptions);
        if (databaseType === "filtered" && (!database || database === "")) {
          if (projectOptions.length > 0) setDatabase(projectOptions[0].value);
        }
        return;
      }

      setFilteredDatabases([]);
    } catch (err) {
      console.error("Error fetching filtered databases:", err);
    }
  };

  const databaseItems = [...databases, ...filteredDatabases];

  const getAvailableDatabases = () => {
    if (databaseType === "filtered") {
      return filteredDatabases;
    } else {
      return databases;
    }
  };

  const getDisplayName = (item) => {
    if (!item) return "";
    if (typeof item === "string") return item.replace(".db", "");
    if (item.label) return item.label;
    if (item.value) return String(item.value).replace(".db", "");
    return "";
  };

  const handleDatabaseTypeChange = (type) => {
    setDatabaseType(type);
    const available = getAvailableDatabases();
    if (available.length > 0) {
      setDatabase(available[0].value || available[0]);
    }
  };

  const handleViewCodebook = (codebookId) => {
    if (codebookId) {
      navigate(`/codebook-view?selected=${codebookId}`);
    } else {
      navigate("/codebook-view");
    }
  };

  const handleSubmit = async (formData) => {
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
      requestData.append("database", formData.database || database);
      if (formData.prompt) requestData.append("prompt", formData.prompt);

      if (!formData.name || !formData.name.trim()) {
        throw new Error("Please provide a name for the generated codebook");
      }
      requestData.append("name", formData.name.trim());
      if (formData.description)
        requestData.append("description", formData.description);

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

  const fields = [
    {
      id: "databaseType",
      label: "Database Type",
      type: "radio",
      value: databaseType,
      options: [
        { value: "unfiltered", label: "Unfiltered Databases" },
        { value: "filtered", label: "Filtered Databases" },
      ],
      onChange: handleDatabaseTypeChange,
    },
    {
      id: "database",
      label: "Select Database",
      type: "select",
      value: database,
      options: getAvailableDatabases().map((item) => ({
        value: item.value || item,
        label: item.label || getDisplayName(item),
      })),
    },
    {
      id: "prompt",
      label: "Enter Prompt",
      type: "textarea",
      value: prompt,
      onChange: (v) => setPrompt(v),
      placeholder:
        "Enter a custom prompt to guide the codebook generation. Leave empty for default behavior.",
      rows: 4,
      extraButtons: [
        {
          label: "Load example prompt",
          onClick: () => setPrompt(EXAMPLE_PROMPT),
          className: "load-prompt-btn",
        },
        {
          label: "Save prompt",
          onClick: async () => {
            try {
              const { api } = await import("../api");

              if (!prompt || !prompt.trim()) {
                alert("Please enter a prompt before saving");
                return;
              }

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
                  `/api/prompts/?prompt_type=${encodeURIComponent("generate")}`
                );
                const prompts = (listRes.data && listRes.data.prompts) || [];
                promptName = `Prompt ${prompts.length + 1}`;
              } catch (e) {
                // fallback to timestamp-based name
              }
              const form = new FormData();
              form.append("promptname", promptName);
              form.append("prompt", prompt.trim());
              form.append("type", "generate");
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
              try {
                setRightView("prompts");
              } catch (e) {}
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
      ],
    },
    {
      id: "name",
      label: "Codebook Name",
      type: "text",
      value: "",
      placeholder: "my-codebook",
    },
    {
      id: "description",
      label: "Description (optional)",
      type: "textarea",
      value: description,
      placeholder: "Optional description for the codebook",
      rows: 2,
      onChange: (v) => setDescription(v),
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
                Generate Codebook
              </h1>

              <div className="action-buttons">
                <button onClick={handleViewCodebook} className="view-button">
                  View Codebook
                </button>
              </div>

              <ActionForm
                fields={fields}
                submitButton={{
                  text: "Generate Codebook",
                  loadingText: "Generating...",
                  disabled: loading,
                }}
                onSubmit={handleSubmit}
                error={error}
                result={result}
                resultTitle="Generated Codebook"
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
          <div className="manager-section">
            <div className="prompt-manager-controls">
              <div className="left-group">
                <button
                  className={rightView === "prompts" ? "active" : ""}
                  onClick={() => setRightView("prompts")}
                >
                  Saved Prompts
                </button>
              </div>
              <div className="right-group">
                <button
                  className={rightView === "codebooks" ? "active" : ""}
                  onClick={() => setRightView("codebooks")}
                >
                  Manage Codebooks
                </button>
              </div>
            </div>

            {rightView === "prompts" ? (
              <PromptManager
                onLoadPrompt={(p) => setPrompt(p)}
                currentPrompt={prompt}
                promptType="generate"
              />
            ) : (
              <CodebookManager
                onViewCodebook={(codebookId) =>
                  navigate(`/codebook-view?selected=${codebookId}`)
                }
              />
            )}
          </div>
        </div>
      </div>
    </>
  );
}
