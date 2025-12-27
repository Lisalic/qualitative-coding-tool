import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import ActionForm from "../components/ActionForm";
import CodebookManager from "../components/CodebookManager";
import "../styles/Home.css";
import "../styles/Data.css";

export default function GenerateCodebook() {
  const navigate = useNavigate();
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
      const response = await fetch("/api/list-databases/");
      if (!response.ok) throw new Error("Failed to fetch databases");
      const data = await response.json();
      setDatabases(data.databases);
      // Set default database if none selected
      if (!database && data.databases.length > 0) {
        setDatabase(data.databases[0]);
      }
    } catch (err) {
      console.error("Error fetching databases:", err);
    }
  };

  const fetchFilteredDatabases = async () => {
    try {
      const response = await fetch("/api/list-filtered-databases/");
      if (!response.ok) throw new Error("Failed to fetch filtered databases");
      const data = await response.json();
      setFilteredDatabases(data.databases);
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
    return item.replace(".db", "");
  };

  const handleDatabaseTypeChange = (type) => {
    setDatabaseType(type);
    const available = getAvailableDatabases();
    if (available.length > 0) {
      setDatabase(available[0]);
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
      requestData.append("database", database);
      requestData.append("api_key", savedApiKey);
      if (formData.prompt) {
        requestData.append("prompt", formData.prompt);
      }

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000);

      const response = await fetch("/api/generate-codebook/", {
        method: "POST",
        body: requestData,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

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
        value: item,
        label: getDisplayName(item),
      })),
    },
    {
      id: "prompt",
      label: "Prompt (Optional)",
      type: "textarea",
      placeholder:
        "Enter a custom prompt to guide the codebook generation. Leave empty for default behavior.",
      rows: 4,
    },
  ];

  return (
    <>
      <Navbar />
      <div className="home-container">
        <div className="page-layout">
          <div className="form-section">
            <div className="form-wrapper">
              <h1>Generate Codebook</h1>

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
