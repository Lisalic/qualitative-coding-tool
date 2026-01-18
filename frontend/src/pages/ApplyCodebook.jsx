import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import ActionForm from "../components/ActionForm";
import CodebookManager from "../components/CodebookManager";
import PromptManager from "../components/PromptManager";
import "../styles/Home.css";
import { apiFetch } from "../api";

export default function ApplyCodebook() {
  const navigate = useNavigate();
  const EXAMPLE_PROMPT = `You are a coding assistant. Given a codebook and an input item, decide which code(s) from the codebook apply and provide a one-sentence justification. Focus on selecting the single best code when applicable; do not invent new codes. Keep responses concise.`;
  const [methodology, setMethodology] = useState("");
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
  const [rightView, setRightView] = useState("codebooks"); // 'codebooks' or 'prompts'
  const [saveMessage, setSaveMessage] = useState("");
  const [saveMessageType, setSaveMessageType] = useState("success");

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
      const list = data.projects || [];
      setProjects(list);
      if (!selectedProject && list.length > 0) {
        setSelectedProject(String(list[0].id));
      }
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
      if (data.codebooks.length > 0 && !codebook) {
        setCodebook(data.codebooks[0].id.toString());
      }
    } catch (err) {
      console.error("Error fetching codebooks:", err);
    }
  };

  const fetchDatabases = async () => {
    try {
      // Prefer server-side Postgres projects for authenticated users
      const projResp = await apiFetch("/api/my-files/?file_type=raw_data");
      if (projResp.ok) {
        const projData = await projResp.json();
        const projects = projData.projects || [];
        const normalized = projects.map((p) => ({
          name: p.schema_name,
          display_name: p.display_name,
          metadata: p,
        }));
        setDatabases(normalized);
        if (!database && normalized.length > 0) setDatabase(normalized[0].name);
        return;
      }

      // Fallback: prefer Postgres projects instead of filesystem list
      const response = await apiFetch("/api/my-files/?file_type=raw_data");
      if (!response.ok) throw new Error("Failed to fetch projects");
      const data = await response.json();
      const normalized = (data.projects || []).map((p) => ({
        name: p.schema_name,
        display_name: p.display_name,
        metadata: p,
      }));
      setDatabases(normalized);
      if (!database && normalized.length > 0) {
        setDatabase(normalized[0].name);
      }
    } catch (err) {
      console.error("Error fetching databases:", err);
    }
  };

  const fetchFilteredDatabases = async () => {
    try {
      // Prefer server-side Postgres projects for authenticated users
      const projResp = await apiFetch("/api/my-files/?file_type=filtered_data");
      if (projResp.ok) {
        const projData = await projResp.json();
        const projects = projData.projects || [];
        const normalized = projects.map((p) => ({
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

  const handleSubmit = async (formData) => {
    const savedApiKey = localStorage.getItem("apiKey");
    if (!savedApiKey) {
      setError("Please set your API key in the navbar first.");
      return;
    }
    if (!formData.report_name || !formData.report_name.trim()) {
      setError(
        "Please provide an output display name (report name) before applying the codebook."
      );
      return;
    }
    try {
      setLoading(true);
      setError(null);
      setResult(null);

      const requestData = new FormData();
      requestData.append("api_key", savedApiKey);
      requestData.append("database", formData.database);
      requestData.append("report_name", formData.report_name);
      requestData.append("codebook", formData.codebook);
      requestData.append("methodology", formData.methodology);
      if (formData.description)
        requestData.append("description", formData.description);
      if (selectedProject) {
        requestData.append("project_id", selectedProject);
      }

      const response = await apiFetch("/api/apply-codebook/", {
        method: "POST",
        body: requestData,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
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
    } else {
      return databases;
    }
  };

  const getDisplayName = (item) => {
    if (!item) return "";
    if (typeof item === "object") return item.display_name || item.name || "";
    return item.replace(".db", "");
  };

  const handleDatabaseTypeChange = (type) => {
    setDatabaseType(type);
    const available = getAvailableDatabases();
    if (available.length > 0) {
      const val = typeof available[0] === "object" ? available[0].name : available[0];
      setDatabase(val);
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
        value: typeof item === "string" ? item : item.name,
        label: getDisplayName(item),
      })),
    },
    {
      id: "project_id",
      label: "Select Project",
      type: "select",
      value: selectedProject,
      onChange: (v) => setSelectedProject(v),
      options: (projects || []).map((p) => ({ value: String(p.id), label: p.projectname || p.display_name || p.name || String(p.id) })),
    },
    {
      id: "codebook",
      label: "Select Codebook",
      type: "select",
      value: codebook,
      options: codebooks.map((cb) => ({
        value: cb.id.toString(),
        label: cb.name || cb.display_name || cb.id.toString(),
      })),
    },
    {
      id: "methodology",
      label: "Enter Prompt",
      type: "textarea",
      value: methodology,
      onChange: (v) => setMethodology(v),
      extraButtons: [
        {
          label: "Load example prompt",
          onClick: () => setMethodology(EXAMPLE_PROMPT),
          className: "load-prompt-btn",
        },
        {
          label: "Save prompt",
          onClick: async () => {
            try {
              const { api } = await import("../api");

              if (!methodology || !methodology.trim()) {
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
                  `/api/prompts/?prompt_type=${encodeURIComponent("apply")}`
                );
                const prompts = (listRes.data && listRes.data.prompts) || [];
                promptName = `Prompt ${prompts.length + 1}`;
              } catch (e) {
                // fallback to timestamp-based name
              }
              const form = new FormData();
              form.append("promptname", promptName);
              form.append("prompt", methodology.trim());
              form.append("type", "apply");
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
      placeholder: "Enter your coding methodology or leave blank...",
      rows: 4,
    },
    {
      id: "report_name",
      label: "Report Name",
      type: "text",
      value: reportName,
      placeholder: "Enter report name... ",
    },
    {
      id: "description",
      label: "Description (optional)",
      type: "textarea",
      value: description,
      placeholder: "Optional description for the report",
      rows: 2,
      onChange: (v) => setDescription(v),
    },
  ];

  return (
    <>
      <div className="home-container">
        <div className="page-layout">
          <div className="left-section">
            <div className="form-wrapper">
              <h1>Apply Codebook</h1>

              <div className="action-buttons">
                <button onClick={handleViewCoding} className="view-button">
                  View Coding Results
                </button>
              </div>

              <ActionForm
                fields={fields}
                submitButton={{
                  text: "Apply Codebook",
                  loadingText: "Applying...",
                  disabled: loading,
                }}
                onSubmit={handleSubmit}
                error={error || (result && result.error)}
                result={result && result.classification_report}
                resultTitle="Classification Report"
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
                onLoadPrompt={(p) => setMethodology(p)}
                currentPrompt={methodology}
                promptType="apply"
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
