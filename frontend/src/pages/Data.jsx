import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import Navbar from "../components/Navbar";
import SelectionList from "../components/SelectionList";
import DataTable from "../components/DataTable";
import "../styles/Data.css";

export default function Data() {
  const navigate = useNavigate();
  const location = useLocation();
  const [databases, setDatabases] = useState([]);
  const [selectedDatabase, setSelectedDatabase] = useState("");

  useEffect(() => {
    fetchDatabases();
  }, []);

  useEffect(() => {
    if (location.state?.selectedDatabase) {
      setSelectedDatabase(location.state.selectedDatabase);
    }
  }, [location.state]);

  useEffect(() => {
    // Set default database if none selected and we have databases loaded
    if (!selectedDatabase && databases.length > 0) {
      setSelectedDatabase(databases[0]);
    }
  }, [databases, selectedDatabase]);

  const fetchDatabases = async () => {
    try {
      const response = await fetch("/api/list-databases/");
      if (!response.ok) throw new Error("Failed to fetch databases");
      const data = await response.json();
      // Handle both old format (array of strings) and new format (array of objects)
      const dbNames = data.databases.map((db) =>
        typeof db === "string" ? db : db.name
      );
      setDatabases(dbNames);
    } catch (err) {
      console.error("Error fetching databases:", err);
    }
  };

  const getTitle = () => {
    if (!selectedDatabase) return "Select a Database";
    return `Database: ${selectedDatabase.replace(".db", "")}`;
  };

  const databaseItems = databases;

  return (
    <>
      <Navbar showBack={true} />
      <div className="data-container">
        <SelectionList
          items={databaseItems.map((d) => ({
            id: d,
            name: d.replace(".db", ""),
          }))}
          selectedId={selectedDatabase}
          onSelect={(id) => setSelectedDatabase(id)}
          className="database-selector"
          buttonClass="db-button"
          emptyMessage="No databases available"
        />
        <DataTable title={getTitle()} database={selectedDatabase} />
      </div>
    </>
  );
}
