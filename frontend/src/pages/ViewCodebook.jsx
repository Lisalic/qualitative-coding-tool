import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import Navbar from "../components/Navbar";
import "../styles/Data.css";
import "../styles/DataTable.css";

export default function ViewCodebook() {
  const navigate = useNavigate();
  const [availableCodebooks, setAvailableCodebooks] = useState([]);
  const [selectedCodebook, setSelectedCodebook] = useState(null);
  const [codebookContent, setCodebookContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState("");
  const [newCodebookName, setNewCodebookName] = useState("");

  const fetchAvailableCodebooks = async () => {
    try {
      const response = await fetch("/api/list-codebooks");
      if (!response.ok) {
        throw new Error("Failed to fetch codebooks list");
      }
      const data = await response.json();
      setAvailableCodebooks(data.codebooks);
      if (data.codebooks.length > 0) {
        const urlParams = new URLSearchParams(window.location.search);
        const selectedFromUrl = urlParams.get("selected");
        if (
          selectedFromUrl &&
          data.codebooks.some((cb) => cb.id === selectedFromUrl)
        ) {
          setSelectedCodebook(selectedFromUrl);
        } else {
          setSelectedCodebook(data.codebooks[data.codebooks.length - 1].id);
        }
      }
    } catch (err) {
      console.error("Error fetching codebooks list:", err);
    }
  };

  const fetchCodebook = async (codebookId) => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`/api/codebook?codebook_id=${codebookId}`);
      if (!response.ok) {
        throw new Error("Failed to fetch codebook");
      }
      const data = await response.json();
      if (data.codebook) {
        setCodebookContent(data.codebook);
        setEditedContent(data.codebook);
        setNewCodebookName(codebookId);
      } else {
        setCodebookContent("");
        setEditedContent("");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = () => {
    setIsEditing(true);
    setEditedContent(codebookContent);
    setNewCodebookName(selectedCodebook);
  };

  const handleSave = async () => {
    if (!newCodebookName.trim()) {
      setError("Codebook name cannot be empty");
      return;
    }

    try {
      const formData = new FormData();
      formData.append("codebook_id", newCodebookName.trim());
      formData.append("content", editedContent);

      const response = await fetch("/api/save-codebook/", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Failed to save codebook");

      const data = await response.json();
      console.log("Codebook saved:", data);

      if (newCodebookName.trim() !== selectedCodebook) {
        setSelectedCodebook(newCodebookName.trim());
        fetchAvailableCodebooks();
      } else {
        setCodebookContent(editedContent);
      }

      setIsEditing(false);
      setError(null);
    } catch (err) {
      console.error("Save error:", err);
      setError(`Error saving codebook: ${err.message}`);
    }
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditedContent(codebookContent);
    setNewCodebookName(selectedCodebook);
    setError(null);
  };

  useEffect(() => {
    fetchAvailableCodebooks();
  }, []);

  useEffect(() => {
    if (selectedCodebook) {
      fetchCodebook(selectedCodebook);
    }
  }, [selectedCodebook]);

  return (
    <>
      <Navbar />
      <div className="data-container">
        <div className="codebook-selector">
          {availableCodebooks.map((cb) => (
            <button
              key={cb.id}
              className={`db-button ${
                selectedCodebook === cb.id ? "active" : ""
              }`}
              onClick={() => setSelectedCodebook(cb.id)}
            >
              {cb.name}
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
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              gap: "20px",
              marginBottom: "20px",
            }}
          >
            {isEditing ? (
              <div
                style={{ display: "flex", alignItems: "center", gap: "10px" }}
              >
                <label style={{ color: "#ffffff" }}>Name:</label>
                <input
                  type="text"
                  value={newCodebookName}
                  onChange={(e) => setNewCodebookName(e.target.value)}
                  style={{
                    padding: "5px 10px",
                    border: "1px solid #ffffff",
                    borderRadius: "4px",
                    backgroundColor: "#000000",
                    color: "#ffffff",
                  }}
                />
                <button
                  onClick={handleSave}
                  className="view-button"
                  style={{ fontSize: "14px", padding: "5px 10px" }}
                >
                  Save
                </button>
                <button
                  onClick={handleCancel}
                  className="view-button"
                  style={{
                    fontSize: "14px",
                    padding: "5px 10px",
                    backgroundColor: "#666",
                  }}
                >
                  Cancel
                </button>
              </div>
            ) : (
              <>
                <h1 style={{ color: "#ffffff", margin: 0 }}>
                  {selectedCodebook ? `${selectedCodebook}` : "View Codebook"}
                </h1>
                {selectedCodebook && (
                  <button
                    onClick={handleEdit}
                    className="view-button"
                    style={{ fontSize: "14px", padding: "8px 16px" }}
                  >
                    Edit
                  </button>
                )}
              </>
            )}
          </div>

          {loading && <p>Loading codebook...</p>}
          {error && <p className="error-message">{error}</p>}

          {codebookContent && (
            <div>
              <div
                style={{
                  backgroundColor: "#000000",
                  border: "1px solid #ffffff",
                  borderRadius: "4px",
                  padding: "20px",
                  color: "#ffffff",
                }}
              >
                {isEditing ? (
                  <textarea
                    value={editedContent}
                    onChange={(e) => setEditedContent(e.target.value)}
                    rows={20}
                    style={{
                      width: "100%",
                      padding: "8px",
                      border: "1px solid #ffffff",
                      borderRadius: "4px",
                      backgroundColor: "#000000",
                      color: "#ffffff",
                      fontFamily: "monospace",
                      resize: "vertical",
                    }}
                    placeholder="Enter codebook content..."
                  />
                ) : (
                  <ReactMarkdown
                    components={{
                      h3: ({ children }) => (
                        <h3 style={{ color: "#ffffff", marginTop: "20px" }}>
                          {children}
                        </h3>
                      ),
                      h4: ({ children }) => (
                        <h4 style={{ color: "#ffffff", marginTop: "15px" }}>
                          {children}
                        </h4>
                      ),
                      ul: ({ children }) => (
                        <ul style={{ color: "#ffffff" }}>{children}</ul>
                      ),
                      li: ({ children }) => (
                        <li style={{ color: "#ffffff" }}>{children}</li>
                      ),
                      strong: ({ children }) => (
                        <strong style={{ color: "#ffffff" }}>{children}</strong>
                      ),
                      p: ({ children }) => (
                        <p style={{ color: "#ffffff" }}>{children}</p>
                      ),
                    }}
                  >
                    {codebookContent}
                  </ReactMarkdown>
                )}
              </div>
            </div>
          )}
          {!codebookContent && !loading && !error && (
            <p>No codebook selected or found. Generate a codebook first.</p>
          )}
        </div>
      </div>
    </>
  );
}
