import { useState, useEffect } from "react";
import { apiFetch } from "../api";
import { useNavigate, useLocation } from "react-router-dom";
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
      const sel = location.state.selectedDatabase;
      const selId = typeof sel === "string" ? sel : sel?.name || sel?.id || "";
      setSelectedDatabase(selId);
    }
  }, [location.state]);

  useEffect(() => {
    if (!selectedDatabase && databases.length > 0) {
      const first = databases[0];
      const id =
        typeof first === "string" ? first : first.name || first.id || "";
      setSelectedDatabase(id);
    }
  }, [databases, selectedDatabase]);

  const fetchFilteredDatabases = async () => {
    try {
      // If user is logged in, fetch their filtered_data projects
      const meResp = await apiFetch("/api/me/");
      if (meResp.ok) {
        const projResp = await apiFetch(
          "/api/my-projects/?project_type=filtered_data"
        );
        if (!projResp.ok) throw new Error("Failed to fetch user projects");
        const projData = await projResp.json();
        const projects = projData.projects || [];
        setUserProjects(projects);
        // normalize to objects with metadata similar to Data.jsx / Import.jsx
        const normalized = projects.map((p) => {
          const tables = p.tables || [];
          const submissionsTable = tables.find(
            (t) => t.table_name === "submissions"
          );
          const commentsTable = tables.find((t) => t.table_name === "comments");
          return {
            name: p.schema_name,
            display_name: p.display_name,
            metadata: {
              created_at: p.created_at || null,
              tables: tables,
              total_submissions: submissionsTable
                ? submissionsTable.row_count
                : 0,
              total_comments: commentsTable ? commentsTable.row_count : 0,
            },
          };
        });
        setDatabases(normalized);
        return;
      }

      setDatabases([]);
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
      <div className="data-container">
        <SelectionList
          items={(databases || []).map((d) => {
            const id = typeof d === "string" ? d : d.name || "";
            const display = userProjects
              ? userProjects.find((p) => p.schema_name === id)?.display_name ||
                (typeof d === "string"
                  ? id.replace(".db", "")
                  : d.display_name || id.replace(".db", ""))
              : typeof d === "string"
              ? id.replace(".db", "")
              : d.display_name || id.replace(".db", "");
            return { id, name: display };
          })}
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
          metadata={
            (databases || []).find(
              (d) =>
                d &&
                (d.name === selectedDatabase ||
                  d.name === String(selectedDatabase).replace(".db", ""))
            )?.metadata
          }
        />
      </div>
    </>
  );
}
