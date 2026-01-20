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
  const [selectedProject, setSelectedProject] = useState("");
  const [projectsList, setProjectsList] = useState([]);

  useEffect(() => {
    fetchFilteredDatabases();
  }, []);

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
        setProjectsList(projects);
        if (!selectedProject) setSelectedProject(String(projects[0].id));
      }
    } catch (err) {
      console.error("Error fetching projects:", err);
    }
  };

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
          "/api/my-files/?file_type=filtered_data",
        );
        if (!projResp.ok) throw new Error("Failed to fetch user projects");
        const projData = await projResp.json();
        const projects = projData.projects || [];
        // Only set userProjects if we don't already have projects from /api/projects/
        if (!userProjects && (!projectsList || projectsList.length === 0))
          setUserProjects(projects);
        // normalize to objects with metadata similar to Data.jsx / Import.jsx
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
        (p) => p.schema_name === selectedDatabase || p.schema_name === baseName,
      );
      return `Database: ${proj ? proj.display_name : baseName}`;
    }
    return `Database: ${baseName}`;
  };

  const getDisplayName = () => {
    if (!selectedDatabase || !userProjects) return null;
    const baseName = selectedDatabase.replace(".db", "");
    const proj = userProjects.find(
      (p) => p.schema_name === selectedDatabase || p.schema_name === baseName,
    );
    return proj ? proj.display_name : null;
  };

  const databaseItems = databases;

  // When selectedProject changes, default selectedDatabase to first filtered file if present
  useEffect(() => {
    if (
      !selectedProject ||
      (!(projectsList && projectsList.length > 0) && !userProjects)
    )
      return;
    const source =
      projectsList && projectsList.length > 0
        ? projectsList
        : userProjects || [];
    const projectObj = source.find(
      (p) => String(p.id) === String(selectedProject),
    );
    const files = (projectObj && projectObj.files) || [];
    const filteredFiles = files.filter((f) => f.file_type === "filtered_data");
    if (filteredFiles.length > 0) {
      const first = filteredFiles[0].schema_name || filteredFiles[0].id || "";
      setSelectedDatabase((cur) => (cur ? cur : first));
    }
  }, [selectedProject, userProjects]);

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
            {(projectsList.length > 0 ? projectsList : userProjects || []).map(
              (p) => (
                <option key={p.id} value={String(p.id)}>
                  {p.projectname || p.display_name || p.schema_name || p.id}
                </option>
              ),
            )}
          </select>
        </div>
        {selectedProject &&
        (projectsList.length > 0 ||
          (userProjects && userProjects.length > 0)) ? (
          (() => {
            const source =
              projectsList.length > 0 ? projectsList : userProjects || [];
            const projectObj = source.find(
              (p) => String(p.id) === String(selectedProject),
            );
            const files = (projectObj && projectObj.files) || [];
            const filteredFiles = files.filter(
              (f) => f.file_type === "filtered_data",
            );
            return (
              <SelectionList
                items={filteredFiles.map((f) => ({
                  id: f.schema_name || f.id,
                  name: f.display_name || f.schema_name || f.id,
                }))}
                selectedId={selectedDatabase}
                onSelect={(id) => setSelectedDatabase(id)}
                className="database-selector"
                buttonClass="db-button"
                emptyMessage={
                  filteredFiles.length
                    ? "No files"
                    : "No filtered files in project"
                }
              />
            );
          })()
        ) : (
          <SelectionList
            items={(databases || []).map((d) => {
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
            emptyMessage="No filtered databases available"
          />
        )}
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
