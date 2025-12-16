import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import ActionForm from "../components/ActionForm";
import "../styles/Home.css";

export default function ApplyCodebook() {
  const navigate = useNavigate();
  const [methodology, setMethodology] = useState("");
  const [database, setDatabase] = useState("original");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

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
      <ActionForm
        title="Apply Codebook"
        viewButton={{
          text: "View Coding Results",
          onClick: handleViewCoding,
        }}
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
    </>
  );
}
