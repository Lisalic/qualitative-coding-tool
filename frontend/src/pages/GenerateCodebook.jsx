import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import ActionForm from "../components/ActionForm";
import CodebookManager from "../components/CodebookManager";
import "../styles/Home.css";

export default function GenerateCodebook() {
  const navigate = useNavigate();
  const [database, setDatabase] = useState("original");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

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
      requestData.append("database", formData.database);
      requestData.append("api_key", savedApiKey);

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
      id: "database",
      label: "Database",
      type: "select",
      value: database,
      options: [
        { value: "original", label: "Reddit Data" },
        { value: "filtered", label: "Filtered Data" },
      ],
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
