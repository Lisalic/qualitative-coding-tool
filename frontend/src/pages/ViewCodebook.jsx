import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import "../styles/Data.css";
import "../styles/DataTable.css";
import MarkdownView from "../components/MarkdownView";
import SelectionList from "../components/SelectionList";

export default function ViewCodebook() {
  const navigate = useNavigate();
  const [availableCodebooks, setAvailableCodebooks] = useState([]);
  const [selectedCodebook, setSelectedCodebook] = useState(null);
  const [codebookContent, setCodebookContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
      } else {
        setCodebookContent("");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
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
        <SelectionList
          items={availableCodebooks}
          selectedId={selectedCodebook}
          onSelect={(id) => setSelectedCodebook(id)}
          className="codebook-selector"
          buttonClass="db-button"
          emptyMessage="No codebooks available"
        />
        <div
          style={{
            border: "1px solid #ffffff",
            borderRadius: "8px",
            padding: "20px",
            backgroundColor: "#000000",
          }}
        >
          <MarkdownView
            selectedId={selectedCodebook}
            fetchStyle="query"
            fetchBase="/api/codebook"
            queryParamName="codebook_id"
            saveUrl="/api/save-codebook/"
            saveIdFieldName="codebook_id"
            onSaved={(newId) => {
              if (newId !== selectedCodebook) {
                setSelectedCodebook(newId);
                fetchAvailableCodebooks();
              }
            }}
            emptyLabel="View Codebook"
          />
          {!codebookContent && !loading && !error && (
            <p>No codebook selected or found. Generate a codebook first.</p>
          )}
        </div>
      </div>
    </>
  );
}
