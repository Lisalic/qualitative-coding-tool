import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import Navbar from "../components/Navbar";
import "../styles/Data.css";

export default function ViewCoding() {
  const navigate = useNavigate();
  const [availableCodedData, setAvailableCodedData] = useState([]);
  const [selectedCodedData, setSelectedCodedData] = useState(null);
  const [codedDataContent, setCodedDataContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const handleBack = () => {
    navigate("/");
  };

  const fetchAvailableCodedData = async () => {
    try {
      const response = await fetch("/api/list-coded-data");
      if (!response.ok) {
        throw new Error("Failed to fetch coded data list");
      }
      const data = await response.json();
      setAvailableCodedData(data.coded_data);
      if (data.coded_data.length > 0) {
        const urlParams = new URLSearchParams(window.location.search);
        const selectedFromUrl = urlParams.get("selected");
        if (
          selectedFromUrl &&
          data.coded_data.some((cd) => cd.id === selectedFromUrl)
        ) {
          setSelectedCodedData(selectedFromUrl);
        } else {
          setSelectedCodedData(data.coded_data[0].id);
        }
      }
    } catch (err) {
      console.error("Error fetching coded data list:", err);
    }
  };

  const fetchCodedData = async (codedDataId) => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`/api/coded-data/${codedDataId}`);
      if (!response.ok) {
        throw new Error("Failed to fetch coded data");
      }
      const data = await response.json();
      if (data.error) {
        setError(data.error);
      } else {
        setCodedDataContent(data.coded_data);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAvailableCodedData();
  }, []);

  useEffect(() => {
    if (selectedCodedData) {
      fetchCodedData(selectedCodedData);
    }
  }, [selectedCodedData]);

  const handleCodedDataChange = (codedDataId) => {
    setSelectedCodedData(codedDataId);
    const url = new URL(window.location);
    url.searchParams.set("selected", codedDataId);
    window.history.pushState({}, "", url);
  };

  return (
    <>
      <Navbar showBack={true} onBack={handleBack} />
      <div className="data-container">
        <div className="codebook-selector">
          {availableCodedData.map((cd) => (
            <button
              key={cd.id}
              className={`db-button ${
                selectedCodedData === cd.id ? "active" : ""
              }`}
              onClick={() => handleCodedDataChange(cd.id)}
            >
              {cd.name}
            </button>
          ))}
        </div>
        <div
          style={{
            border: "1px solid #ffffff",
            borderRadius: "8px",
            padding: "20px",
            backgroundColor: "#000000",
          }}
        >
          <h1 style={{ textAlign: "center", color: "#ffffff" }}>
            {selectedCodedData ? `${selectedCodedData}` : "View Coding"}
          </h1>

          {loading && <p style={{ color: "#ffffff" }}>Loading coded data...</p>}
          {error && (
            <div
              style={{
                color: "#ff6666",
                padding: "10px",
                border: "1px solid #ff6666",
                borderRadius: "4px",
                marginBottom: "20px",
              }}
            >
              {error}
            </div>
          )}

          {codedDataContent && (
            <div>
              <div
                style={{
                  backgroundColor: "#000000",
                  border: "1px solid #ffffff",
                  borderRadius: "4px",
                  padding: "20px",
                  color: "#ffffff",
                  maxHeight: "70vh",
                  overflowY: "auto",
                }}
              >
                <pre
                  style={{
                    color: "#ffffff",
                    whiteSpace: "pre-wrap",
                    fontFamily: "monospace",
                    fontSize: "14px",
                    margin: 0,
                    lineHeight: "1.5",
                  }}
                >
                  {codedDataContent}
                </pre>
              </div>
            </div>
          )}

          {!loading && !error && !codedDataContent && selectedCodedData && (
            <p style={{ color: "#ffffff" }}>
              No coded data found for {selectedCodedData}.
            </p>
          )}
        </div>
      </div>
    </>
  );
}
