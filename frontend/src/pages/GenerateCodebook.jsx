import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import ActionForm from "../components/ActionForm";
import CodebookManager from "../components/CodebookManager";
import "../styles/Home.css";
import "../styles/Data.css";

export default function GenerateCodebook() {
  const navigate = useNavigate();
  // Example prompt provided by user for codebook generation
  const EXAMPLE_PROMPT = `You are a codebook generator. Read representative dataset excerpts and propose a concise codebook of [topic]. Keep entries concise and focused; do not add unrelated commentary.`;
  const [prompt, setPrompt] = useState("");
  const [database, setDatabase] = useState("");
  const [databaseType, setDatabaseType] = useState("unfiltered");
  const [databases, setDatabases] = useState([]);
  const [filteredDatabases, setFilteredDatabases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDatabases();
    fetchFilteredDatabases();
  }, []);

  const fetchDatabases = async () => {
    try {
      // Prefer Postgres projects; list-databases removed in favor of my-projects
      const response = await fetch("/api/my-projects/?project_type=raw_data", {
        credentials: "include",
      });
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
      const projResp = await fetch(
        "/api/my-projects/?project_type=filtered_data",
        { credentials: "include" }
      );
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

      const response = await fetch("/api/list-filtered-databases/", {
        credentials: "include",
      });
      if (!response.ok) throw new Error("Failed to fetch filtered databases");
      const data = await response.json();
      const fdOptions = (data.databases || []).map((d) => {
        const name = typeof d === "string" ? d : d.name;
        return { value: name, label: name.replace(/\.db$/, ""), meta: d };
      });
      setFilteredDatabases(fdOptions);
      if (databaseType === "filtered" && (!database || database === "")) {
        if (fdOptions.length > 0) setDatabase(fdOptions[0].value);
      }
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

      const response = await fetch("/api/generate-codebook/", {
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
      label: "Specific Database",
      type: "select",
      value: database,
      options: getAvailableDatabases().map((item) => ({
        value: item.value || item,
        label: item.label || getDisplayName(item),
      })),
    },
    {
      id: "prompt",
      label: "Prompt (Optional)",
      type: "textarea",
      value: prompt,
      placeholder:
        "Enter a custom prompt to guide the codebook generation. Leave empty for default behavior.",
      rows: 4,
      extraButton: {
        label: "Load example prompt",
        onClick: () => setPrompt(EXAMPLE_PROMPT),
        className: "load-prompt-btn",
      },
    },
    {
      id: "name",
      label: "Codebook Name",
      type: "text",
      value: "",
      placeholder: "my-codebook",
    },
  ];

  return (
    <>
      <Navbar />
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
            </div>
          </div>
          <div className="manager-section">
            <CodebookManager
              onViewCodebook={(codebookId) =>
                navigate(`/codebook-view?selected=${codebookId}`)
              }
            />
          </div>
        </div>
      </div>
    </>
  );
}
