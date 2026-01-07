import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
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
  const [codebooks, setCodebooks] = useState([]);
  const [databases, setDatabases] = useState([]);
  const [filteredDatabases, setFilteredDatabases] = useState([]);
  const [rightView, setRightView] = useState("codebooks"); // 'codebooks' or 'prompts'

  useEffect(() => {
    fetchCodebooks();
    fetchDatabases();
    fetchFilteredDatabases();
  }, []);

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
      const projResp = await apiFetch(
        "/api/my-projects/?project_type=raw_data"
      );
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
      const response = await apiFetch(
        "/api/my-projects/?project_type=raw_data"
      );
      if (!response.ok) throw new Error("Failed to fetch projects");
      const data = await response.json();
      const normalized = (data.projects || []).map((p) => ({
        name: p.schema_name,
        display_name: p.display_name,
        metadata: p,
      }));
      setDatabases(normalized);
      if (!database && dbNames.length > 0) {
        setDatabase(dbNames[0]);
      }
    } catch (err) {
      console.error("Error fetching databases:", err);
    }
  };

  const fetchFilteredDatabases = async () => {
    try {
      // Prefer server-side Postgres projects for authenticated users
      const projResp = await apiFetch(
        "/api/my-projects/?project_type=filtered_data"
      );
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
      setDatabase(available[0]);
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
      label: "Specific Database",
      type: "select",
      value: database,
      options: getAvailableDatabases().map((item) => ({
        value: typeof item === "string" ? item : item.name,
        label: getDisplayName(item),
      })),
    },
    {
      id: "codebook",
      label: "Codebook",
      type: "select",
      value: codebook,
      options: codebooks.map((cb) => ({
        value: cb.id.toString(),
        label: cb.name || cb.display_name || cb.id.toString(),
      })),
    },
    {
      id: "methodology",
      label: "Methodology (Optional)",
      type: "textarea",
      value: methodology,
      extraButton: {
        label: "Load example prompt",
        onClick: () => setMethodology(EXAMPLE_PROMPT),
        className: "load-prompt-btn",
      },
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
  ];

  return (
    <>
      <Navbar />
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
            </div>
          </div>
          <div className="manager-section">
            <div className="prompt-manager-controls">
              <div className="left-group">
                <button
                  className={rightView === "prompts" ? "active" : ""}
                  onClick={() => setRightView("prompts")}
                >
                  Manage Prompts
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
