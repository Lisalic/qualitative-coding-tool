import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import ActionForm from "../components/ActionForm";
import PromptManager from "../components/PromptManager";
import { useState, useEffect } from "react";
import "../styles/Home.css";

export default function Filter() {
  const navigate = useNavigate();
  const [filterPrompt, setFilterPrompt] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [database, setDatabase] = useState("");
  const [databases, setDatabases] = useState([]);
  const [name, setName] = useState("");

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
    if (databases.length > 0 && !database) {
      setDatabase(databases[0]);
    }
  }, [databases]);

  const fetchDatabases = async () => {
    try {
      const response = await fetch("/api/list-databases/");
      if (!response.ok) throw new Error("Failed to fetch databases");
      const data = await response.json();
      const dbNames = (data.databases || []).map((d) =>
        typeof d === "string" ? d : d.name
      );
      setDatabases(dbNames);
      if (!database && dbNames.length > 0) setDatabase(dbNames[0]);
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
  };

  const handleSubmit = async (formData) => {
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
      // include desired output name if provided
      if (formData.name) {
        requestData.append("name", formData.name);
      }
      // include selected database if provided
      if (formData.database) {
        requestData.append("database", formData.database);
      }

      const response = await fetch("/api/filter-data/", {
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
      label: "Enter or load a prompt to filter",
      type: "textarea",
      value: filterPrompt,
      placeholder: "Enter your filter prompt...",
      rows: 5,
    },
  ];

  const nameField = {
    id: "name",
    label: "Filtered Database Name",
    type: "text",
    value: name,
    placeholder: "my-filtered-db",
  };

  const databaseFields = [
    {
      id: "database",
      label: "Database",
      type: "select",
      value: database,
      options: databases.map((d) => ({
        value: d,
        label: d.replace(".db", ""),
      })),
    },
  ];

  return (
    <>
      <Navbar showBack={true} />
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
              <ActionForm
                fields={[...databaseFields, nameField, ...fields]}
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
            </div>
          </div>
          <div className="prompt-manager-section">
            <PromptManager
              onLoadPrompt={handleLoadPrompt}
              currentPrompt={filterPrompt}
            />
          </div>
        </div>
      </div>
    </>
  );
}
