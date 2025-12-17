import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import DataTable from "../components/DataTable";
import "../styles/Data.css";

export default function Data() {
  const navigate = useNavigate();
  const [databases, setDatabases] = useState([]);
  const [selectedDatabase, setSelectedDatabase] = useState("original");

  useEffect(() => {
    fetchDatabases();
  }, []);

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

  const handleBack = () => {
    navigate("/");
  };

  const getTitle = () => {
    if (selectedDatabase === "original") return "Master Database Contents";
    return `Database: ${selectedDatabase.replace(".db", "")}`;
  };

  return (
    <>
      <Navbar showBack={true} onBack={handleBack} />
      <div className="data-container">
        <div className="database-selector">
          <button
            className={`db-button ${
              selectedDatabase === "original" ? "active" : ""
            }`}
            onClick={() => setSelectedDatabase("original")}
          >
            Master Database
          </button>
          {databases.map((db) => (
            <button
              key={db}
              className={`db-button ${selectedDatabase === db ? "active" : ""}`}
              onClick={() => setSelectedDatabase(db)}
            >
              {db.replace(".db", "")}
            </button>
          ))}
        </div>
        <DataTable title={getTitle()} database={selectedDatabase} />
      </div>
    </>
  );
}
