import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import ActionForm from "../components/ActionForm";
import CodebookManager from "../components/CodebookManager";
import "../styles/Home.css";

export default function ApplyCodebook() {
  const navigate = useNavigate();
  const [methodology, setMethodology] = useState("");
  const [database, setDatabase] = useState("original");
  const [codebook, setCodebook] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [codebooks, setCodebooks] = useState([]);

  useEffect(() => {
    fetchCodebooks();
  }, []);

  const fetchCodebooks = async () => {
    try {
      const response = await fetch("/api/list-codebooks");
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

  const handleViewCoding = () => {
    navigate("/coding-view");
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
      requestData.append("database", formData.database);
      requestData.append("codebook", formData.codebook);
      requestData.append("methodology", formData.methodology);

      const response = await fetch("/api/apply-codebook/", {
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

  const fields = [
    {
      id: "database",
      label: "Data Source",
      type: "select",
      value: database,
      options: [
        { value: "original", label: "Original Data" },
        { value: "filtered", label: "Filtered Data" },
      ],
    },
    {
      id: "codebook",
      label: "Codebook",
      type: "select",
      value: codebook,
      options: codebooks.map((cb) => ({
        value: cb.id.toString(),
        label: cb.id.toString(),
      })),
    },
    {
      id: "methodology",
      label: "Methodology (Optional)",
      type: "textarea",
      value: methodology,
      placeholder: "Enter your coding methodology or leave blank...",
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
            Apply Codebook
          </h1>
          <div style={{ marginBottom: "30px", textAlign: "center" }}>
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
        <CodebookManager
          onViewCodebook={(codebookId) =>
            navigate(`/codebook-view?selected=${codebookId}`)
          }
        />
      </div>
    </>
  );
}
