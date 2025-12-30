import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import Navbar from "../components/Navbar";
import SelectionList from "../components/SelectionList";
import DataTable from "../components/DataTable";
import "../styles/Data.css";

export default function FilteredData() {
  const navigate = useNavigate();
  const location = useLocation();
  const [databases, setDatabases] = useState([]);
  const [selectedDatabase, setSelectedDatabase] = useState("");
  const [userProjects, setUserProjects] = useState(null);

  useEffect(() => {
    fetchFilteredDatabases();
  }, []);

  useEffect(() => {
    if (location.state?.selectedDatabase) {
      setSelectedDatabase(location.state.selectedDatabase);
    }
  }, [location.state]);

  useEffect(() => {
    if (!selectedDatabase && databases.length > 0) {
      setSelectedDatabase(databases[0]);
    }
  }, [databases, selectedDatabase]);

  const fetchFilteredDatabases = async () => {
    try {
      // If user is logged in, fetch their filtered_data projects
      const meResp = await fetch("/api/me/", { credentials: "include" });
      if (meResp.ok) {
        const projResp = await fetch(
          "/api/my-projects/?project_type=filtered_data",
          { credentials: "include" }
        );
        if (!projResp.ok) throw new Error("Failed to fetch user projects");
        const projData = await projResp.json();
        setUserProjects(projData.projects || []);
        setDatabases((projData.projects || []).map((p) => p.schema_name));
        return;
      }

      const response = await fetch("/api/list-filtered-databases/");
      if (!response.ok) throw new Error("Failed to fetch filtered databases");
      const data = await response.json();
      const dbNames = (data.databases || []).map((db) =>
        typeof db === "string" ? db : db.name
      );
      setDatabases(dbNames);
    } catch (err) {
      console.error("Error fetching filtered databases:", err);
    }
  };

  const getTitle = () => {
    if (!selectedDatabase) return "Select a Database";
    const baseName = selectedDatabase.replace(".db", "");
    if (userProjects) {
      const proj = userProjects.find(
        (p) => p.schema_name === selectedDatabase || p.schema_name === baseName
      );
      return `Database: ${proj ? proj.display_name : baseName}`;
    }
    return `Database: ${baseName}`;
  };

  const getDisplayName = () => {
    if (!selectedDatabase || !userProjects) return null;
    const baseName = selectedDatabase.replace(".db", "");
    const proj = userProjects.find(
      (p) => p.schema_name === selectedDatabase || p.schema_name === baseName
    );
    return proj ? proj.display_name : null;
  };

  const databaseItems = databases;

  return (
    <>
      <Navbar showBack={true} />
      <div className="data-container">
        <SelectionList
          items={databaseItems.map((d) => ({
            id: d,
            name: userProjects
              ? userProjects.find((p) => p.schema_name === d)?.display_name ||
                d.replace(".db", "")
              : d.replace(".db", ""),
          }))}
          selectedId={selectedDatabase}
          onSelect={(id) => setSelectedDatabase(id)}
          className="database-selector"
          buttonClass="db-button"
          emptyMessage="No filtered databases available"
        />
        <DataTable
          title={getTitle()}
          database={selectedDatabase}
          isFilteredView={true}
          displayName={getDisplayName()}
        />
      </div>
    </>
  );
}
