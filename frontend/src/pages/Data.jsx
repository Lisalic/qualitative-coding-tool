import { useState, useEffect } from "react";
import { apiFetch } from "../api";
import { useNavigate, useLocation } from "react-router-dom";
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
      const sel = location.state.selectedDatabase;
      const selId = typeof sel === "string" ? sel : sel?.name || sel?.id || "";
      setSelectedDatabase(selId);
    }
  }, [location.state]);

  useEffect(() => {
    // Set default database if none selected and we have databases loaded
    if (!selectedDatabase && databases.length > 0) {
      const first = databases[0];
      const id =
        typeof first === "string" ? first : first.name || first.id || "";
      setSelectedDatabase(id);
    }
  }, [databases, selectedDatabase]);

  const fetchDatabases = async () => {
    try {
      // Check if user is logged in
      const meResp = await apiFetch("/api/me/");
      if (meResp.ok) {
        // user is authenticated; fetch their raw_data projects
        const projResp = await apiFetch("/api/my-files/?file_type=raw_data");
        if (!projResp.ok) throw new Error("Failed to fetch user projects");
        const projData = await projResp.json();
        const projects = projData.projects || [];
        setUserProjects(projects);
        const normalized = projects.map((p) => {
          const tables = p.tables || [];
          const submissionsTable = tables.find(
            (t) => t.table_name === "submissions"
          );
          const commentsTable = tables.find((t) => t.table_name === "comments");
          return {
            name: p.schema_name,
            display_name: p.display_name,
            description: p.description ?? null,
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

      // Not authenticated — try my-projects for raw_data (may return empty)
      const response = await apiFetch("/api/my-files/?file_type=raw_data");
      if (response.ok) {
        const projData = await response.json();
        const projects = projData.projects || [];
        setUserProjects(projects);
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
    } catch (err) {
      console.error("Error fetching databases or projects:", err);
    }
  };

  const getTitle = () => {
    if (!selectedDatabase) return "Select a Database";
    const baseName = String(selectedDatabase).replace(".db", "");
    // attempt to find a normalized database object in `databases`
    const projObj = (databases || []).find(
      (d) => d && (d.name === selectedDatabase || d.name === baseName)
    );
    if (projObj) return `Database: ${projObj.display_name || baseName}`;
    return `Database: ${baseName}`;
  };

  const getDisplayName = () => {
    if (!selectedDatabase) return null;
    const baseName = String(selectedDatabase).replace(".db", "");
    const projObj = (databases || []).find(
      (d) => d && (d.name === selectedDatabase || d.name === baseName)
    );
    return projObj ? projObj.display_name : null;
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
          emptyMessage={
            userProjects ? "No projects available" : "No databases available"
          }
        />
        <DataTable
          title={getTitle()}
          database={selectedDatabase}
          displayName={getDisplayName()}
          metadata={
            (databases || []).find(
              (d) =>
                d &&
                (d.name === selectedDatabase ||
                  d.name === String(selectedDatabase).replace(".db", ""))
            )?.metadata
          }
          description={
            (databases || []).find(
              (d) =>
                d &&
                (d.name === selectedDatabase ||
                  d.name === String(selectedDatabase).replace(".db", ""))
            )?.description
          }
        />
      </div>
    </>
  );
}
