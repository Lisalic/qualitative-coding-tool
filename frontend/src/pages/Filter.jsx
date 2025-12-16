import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import ActionForm from "../components/ActionForm";
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
      label: "Filter Prompt",
      type: "textarea",
      value: filterPrompt,
      placeholder: "Enter your filter prompt...",
      rows: 5,
    },
  ];

  return (
    <>
      <Navbar showBack={true} onBack={handleBack} />
      <ActionForm
        title="Filter Data"
        viewButton={{
          text: "View Filtered Data",
          onClick: handleViewFilteredData,
        }}
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
    </>
  );
}
