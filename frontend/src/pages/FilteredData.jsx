import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Navbar from "../components/Navbar";
import DataTable from "../components/DataTable";
import "../styles/Data.css";

export default function FilteredData() {
  const navigate = useNavigate();
  const [databases, setDatabases] = useState([]);
  const [selectedDatabase, setSelectedDatabase] = useState("");

  useEffect(() => {
    fetchFilteredDatabases();
  }, []);

  const fetchFilteredDatabases = async () => {
    try {
      const response = await fetch("/api/list-filtered-databases/");
      if (!response.ok) throw new Error("Failed to fetch filtered databases");
      const data = await response.json();
      setDatabases(data.databases);
      if (data.databases.length > 0 && !selectedDatabase) {
        setSelectedDatabase(data.databases[0]);
      }
    } catch (err) {
      console.error("Error fetching filtered databases:", err);
    }
  };

  const getTitle = () => {
    if (!selectedDatabase) return "Filtered Data Contents";
    return `Filtered Database: ${selectedDatabase.replace(".db", "")}`;
  };

  const databaseItems = databases;

  const getDisplayName = (item) => {
    return item.replace(".db", "");
  };

  return (
    <>
      <Navbar showBack={true} />
      <div className="data-container">
        {databases.length > 0 ? (
          <>
            <div className="database-selector">
              {databaseItems.map((item) => {
                const itemId = item;
                const displayName = getDisplayName(item);
                return (
                  <button
                    key={itemId}
                    className={`db-button ${
                      selectedDatabase === itemId ? "active" : ""
                    }`}
                    onClick={() => setSelectedDatabase(itemId)}
                  >
                    {displayName}
                  </button>
                );
              })}
            </div>
            <DataTable
              title={getTitle()}
              database={selectedDatabase}
              isFilteredView={true}
            />
          </>
        ) : (
          <div style={{ textAlign: "center", padding: "20px" }}>
            <p>
              No filtered databases available. Please create filtered data
              first.
            </p>
          </div>
        )}
      </div>
    </>
  );
}
