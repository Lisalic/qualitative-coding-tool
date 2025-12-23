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
  const [databaseType, setDatabaseType] = useState("unfiltered");
  const [codebook, setCodebook] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [codebooks, setCodebooks] = useState([]);
  const [databases, setDatabases] = useState([]);
  const [filteredDatabases, setFilteredDatabases] = useState([]);

  useEffect(() => {
    fetchCodebooks();
    fetchDatabases();
    fetchFilteredDatabases();
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

  const getAvailableDatabases = () => {
    if (databaseType === "filtered") {
      return filteredDatabases;
    } else {
      return ["original", ...databases];
    }
  };

  const getDisplayName = (item) => {
    if (item === "original") return "Master Database";
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
        value: item,
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

        <CodebookManager
          onViewCodebook={(codebookId) =>
            navigate(`/codebook-view?selected=${codebookId}`)
          }
        />
      </div>
    </>
  );
}
