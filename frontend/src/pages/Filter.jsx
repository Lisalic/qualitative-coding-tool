import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import ActionForm from "../components/ActionForm";
import PromptManager from "../components/PromptManager";
import { useState } from "react";
import "../styles/Home.css";

export default function Filter() {
  const navigate = useNavigate();
  const [filterPrompt, setFilterPrompt] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const handleBack = () => {
    navigate("/");
  };

  const handleViewFilteredData = () => {
    navigate("/filtered-data");
  };

  const handleLoadPrompt = (prompt) => {
    setFilterPrompt(prompt);
  };

  const handleFieldChange = (fieldId, value) => {
    if (fieldId === "filterPrompt") {
      setFilterPrompt(value);
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

    setLoading(true);
    setMessage("");

    try {
      const requestData = new FormData();
      requestData.append("api_key", savedApiKey);
      requestData.append("prompt", formData.filterPrompt);

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

  return (
    <>
      <Navbar showBack={true} onBack={handleBack} />
      <div className="home-container">
        <div className="filter-layout">
          <div style={{ textAlign: "center", marginBottom: "30px" }}>
            <h1 style={{ fontSize: "28px", fontWeight: "600" }}>Filter Data</h1>
            <button
              type="button"
              onClick={handleViewFilteredData}
              style={{
                backgroundColor: "#000000",
                color: "#ffffff",
                border: "1px solid #ffffff",
                padding: "12px 24px",
                fontSize: "16px",
                cursor: "pointer",
                borderRadius: "4px",
                marginTop: "10px",
                transition: "all 0.2s",
              }}
              onMouseOver={(e) => {
                e.target.style.backgroundColor = "#ffffff";
                e.target.style.color = "#000000";
              }}
              onMouseOut={(e) => {
                e.target.style.backgroundColor = "#000000";
                e.target.style.color = "#ffffff";
              }}
            >
              View Filtered Data
            </button>
          </div>
          <div style={{ display: "flex", gap: "30px" }}>
            <div className="filter-form-section">
              <h1
                style={{
                  textAlign: "center",
                  fontSize: "28px",
                  fontWeight: "600",
                  margin: "0 0 30px 0",
                }}
              >
                Apply Filter
              </h1>
              <ActionForm
                title="Filter Prompt"
                fields={fields}
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
            <div className="prompt-manager-section">
              <PromptManager
                onLoadPrompt={handleLoadPrompt}
                currentPrompt={filterPrompt}
              />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
