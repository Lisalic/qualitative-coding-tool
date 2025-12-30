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
  const [userProjects, setUserProjects] = useState(null);

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
      // Check if user is logged in
      const meResp = await fetch("/api/me/", { credentials: "include" });
      if (meResp.ok) {
        // user is authenticated; fetch their raw_data projects
        const projResp = await fetch(
          "/api/my-projects/?project_type=raw_data",
          {
            credentials: "include",
          }
        );
        if (!projResp.ok) throw new Error("Failed to fetch user projects");
        const projData = await projResp.json();
        // projects come as objects with display_name and schema_name
        setUserProjects(projData.projects || []);
        // represent them in the existing `databases` state as schema_name for compatibility
        setDatabases((projData.projects || []).map((p) => p.schema_name));
        return;
      }

      // Not authenticated — fall back to listing uploaded databases
      const response = await fetch("/api/list-databases/");
      if (!response.ok) throw new Error("Failed to fetch databases");
      const data = await response.json();
      // Handle both old format (array of strings) and new format (array of objects)
      const dbNames = data.databases.map((db) =>
        typeof db === "string" ? db : db.name
      );
      setDatabases(dbNames);
    } catch (err) {
      console.error("Error fetching databases or projects:", err);
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
          emptyMessage={
            userProjects ? "No projects available" : "No databases available"
          }
        />
        <DataTable
          title={getTitle()}
          database={selectedDatabase}
          displayName={getDisplayName()}
        />
      </div>
    </>
  );
}
