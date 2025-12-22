import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import ActionForm from "../components/ActionForm";
import CodebookManager from "../components/CodebookManager";
import "../styles/Home.css";
import "../styles/Data.css";

export default function GenerateCodebook() {
  const navigate = useNavigate();
  const [database, setDatabase] = useState("original");
  const [databases, setDatabases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchDatabases();
  }, []);

  const fetchDatabases = async () => {
    try {
      const response = await fetch("/api/list-databases/");
      if (!response.ok) throw new Error("Failed to fetch databases");
      const data = await response.json();
      setDatabases(data.databases);
    } catch (err) {
      console.error("Error fetching databases:", err);
    }
  };

  const databaseItems = ["original", ...databases];

  const getDisplayName = (item) => {
    if (item === "original") return "Master Database";
    return item.replace(".db", "");
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
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            border: "2px solid #ffffff",
            borderRadius: "8px",
            padding: "20px",
          }}
        >
          <h1
            style={{
              fontSize: "28px",
              fontWeight: "600",
              margin: "0 0 30px 0",
              textAlign: "center",
            }}
          >
            Generate Codebook
          </h1>
          <div style={{ marginBottom: "30px", textAlign: "center" }}>
            <button onClick={handleViewCodebook} className="view-button">
              View Codebook
            </button>
          </div>
          <div className="database-selector">
            <h3 style={{ marginBottom: "15px", color: "#ffffff" }}>
              Select Database
            </h3>
            {databaseItems.map((item) => {
              const itemId = item;
              const displayName = getDisplayName(item);
              return (
                <button
                  key={itemId}
                  className={`db-button ${database === itemId ? "active" : ""}`}
                  onClick={() => setDatabase(itemId)}
                >
                  {displayName}
                </button>
              );
            })}
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
        <CodebookManager
          onViewCodebook={(codebookId) =>
            navigate(`/codebook-view?selected=${codebookId}`)
          }
        />
      </div>
    </>
  );
}
