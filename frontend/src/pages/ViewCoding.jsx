import { useState, useEffect } from "react";
import Navbar from "../components/Navbar";
import SelectionList from "../components/SelectionList";
import "../styles/Data.css";
import "../styles/DataTable.css";
import MarkdownView from "../components/MarkdownView";

export default function ViewCoding() {
  const [availableCodedData, setAvailableCodedData] = useState([]);
  const [selectedCodedData, setSelectedCodedData] = useState(null);

  const fetchAvailableCodedData = async () => {
    try {
      const response = await fetch("/api/list-coded-data");
      if (!response.ok) throw new Error("Failed to fetch coded data list");
      const data = await response.json();
      setAvailableCodedData(data.coded_data || []);
      if ((data.coded_data || []).length > 0) {
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

  useEffect(() => {
    fetchAvailableCodedData();
  }, []);

  const handleCodedDataChange = (codedDataId) => {
    setSelectedCodedData(codedDataId);
    const url = new URL(window.location);
    url.searchParams.set("selected", codedDataId);
    window.history.pushState({}, "", url);
  };

  return (
    <>
      <Navbar showBack={true} />
      <div className="data-container">
        <SelectionList
          items={availableCodedData}
          selectedId={selectedCodedData}
          onSelect={(id) => handleCodedDataChange(id)}
          className="codebook-selector"
          buttonClass="db-button"
          emptyMessage="No coded data available"
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
            selectedId={selectedCodedData}
            fetchStyle="path"
            fetchBase="/api/coded-data"
            queryParamName=""
            saveUrl="/api/save-coded-data/"
            saveIdFieldName="coded_id"
            onSaved={(newId) => {
              if (newId !== selectedCodedData) {
                setSelectedCodedData(newId);
                fetchAvailableCodedData();
              }
            }}
            emptyLabel="View Coding"
          />
        </div>
      </div>
    </>
  );
}
