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
  const [selectedProject, setSelectedProject] = useState("");

  // prefer projects endpoint which includes files; fall back to my-files
  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const resp = await apiFetch("/api/projects/");
      if (!resp.ok) return;
      const data = await resp.json();
      const projects = data.projects || [];
      if (projects.length > 0) {
        setUserProjects(projects);
        // set default selected project if none
        if (!selectedProject) {
          setSelectedProject(String(projects[0].id || ""));
        }
      }
    } catch (err) {
      console.error("Error fetching projects:", err);
    }
  };

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

  useEffect(() => {
    // When projects load, set a default selected project
    if (!selectedProject && userProjects && userProjects.length > 0) {
      setSelectedProject(String(userProjects[0].id || ""));
    }
  }, [userProjects, selectedProject]);

  // When selected project changes, ensure selectedDatabase defaults to first file in project
  useEffect(() => {
    if (!selectedProject || !userProjects) return;
    const projectObj = userProjects.find(
      (p) =>
        String(p.schema_name) === String(selectedProject) ||
        String(p.id) === String(selectedProject),
    );
    const files = (projectObj && projectObj.files) || [];
    if (files.length > 0) {
      const firstFile = files[0].schema_name || files[0].id || "";
      setSelectedDatabase((cur) => (cur ? cur : firstFile));
    }
  }, [selectedProject, userProjects]);

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
        const normalized = projects.map((p) => {
          const tables = p.tables || [];
          const submissionsTable = tables.find(
            (t) => t.table_name === "submissions",
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
        const normalized = projects.map((p) => {
          const tables = p.tables || [];
          const submissionsTable = tables.find(
            (t) => t.table_name === "submissions",
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
      (d) => d && (d.name === selectedDatabase || d.name === baseName),
    );
    if (projObj) return `Database: ${projObj.display_name || baseName}`;
    return `Database: ${baseName}`;
  };

  const getDisplayName = () => {
    if (!selectedDatabase) return null;
    const baseName = String(selectedDatabase).replace(".db", "");
    const projObj = (databases || []).find(
      (d) => d && (d.name === selectedDatabase || d.name === baseName),
    );
    return projObj ? projObj.display_name : null;
  };

  const databaseItems = databases.filter((d) => {
    // If a project is selected and we have project files, show those files
    if (selectedProject && userProjects && userProjects.length > 0) {
      const projectObj = userProjects.find(
        (p) => String(p.id) === String(selectedProject),
      );
      if (projectObj && projectObj.files && projectObj.files.length > 0) {
        return false; // we won't use this filtered list; SelectionList will use projectObj.files
      }
    }
    if (!selectedProject) return true;
    const id = d.name || d.id || "";
    return String(id) === String(selectedProject);
  });

  return (
    <>
      <div className="data-container">
        <div style={{ marginBottom: 12 }}>
          <label style={{ color: "#fff", marginRight: 8 }}>Project:</label>
          <select
            value={selectedProject}
            onChange={(e) => setSelectedProject(e.target.value)}
            style={{ padding: "6px 8px", borderRadius: 6 }}
          >
            <option value="">All Projects</option>
            {(userProjects || []).map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.projectname || p.display_name || p.schema_name || p.id}
              </option>
            ))}
          </select>
        </div>
        {selectedProject && userProjects && userProjects.length > 0 ? (
          (() => {
            const projectObj = userProjects.find(
              (p) => String(p.id) === String(selectedProject),
            );
            const files = (projectObj && projectObj.files) || [];
            return (
              <SelectionList
                items={files.map((f) => ({
                  id: f.schema_name || f.id,
                  name: f.display_name || f.schema_name || f.id,
                }))}
                selectedId={selectedDatabase}
                onSelect={(id) => setSelectedDatabase(id)}
                className="database-selector"
                buttonClass="db-button"
                emptyMessage={files.length ? "No files" : "No files in project"}
              />
            );
          })()
        ) : (
          <SelectionList
            items={(databaseItems || []).map((d) => {
              const id = typeof d === "string" ? d : d.name || "";
              const display = userProjects
                ? userProjects.find((p) => p.schema_name === id)
                    ?.display_name ||
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
        )}
        <DataTable
          title={getTitle()}
          database={selectedDatabase}
          displayName={getDisplayName()}
          metadata={
            (databases || []).find(
              (d) =>
                d &&
                (d.name === selectedDatabase ||
                  d.name === String(selectedDatabase).replace(".db", "")),
            )?.metadata
          }
          description={
            (databases || []).find(
              (d) =>
                d &&
                (d.name === selectedDatabase ||
                  d.name === String(selectedDatabase).replace(".db", "")),
            )?.description
          }
        />
      </div>
    </>
  );
}
