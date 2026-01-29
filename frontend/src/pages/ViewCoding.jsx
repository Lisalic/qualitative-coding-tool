import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch } from "../api";
import SelectionList from "../components/SelectionList";
import "../styles/Data.css";
import "../styles/DataTable.css";
import MarkdownView from "../components/MarkdownView";

export default function ViewCoding() {
  const location = useLocation();
  const [availableCodedData, setAvailableCodedData] = useState([]);
  const [selectedCodedData, setSelectedCodedData] = useState(null);
  const [selectedCodedDataName, setSelectedCodedDataName] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [projectsList, setProjectsList] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");

  const fetchAvailableCodedData = async () => {
    try {
      // Prefer project-backed files when a project is selected
      if (projectsList && projectsList.length > 0 && selectedProject) {
        const projectObj = projectsList.find(
          (p) => String(p.id) === String(selectedProject),
        );
        const files = (projectObj && projectObj.files) || [];
        const codingFiles = files
          .filter(
            (f) =>
              f.file_type === "coding" || f.file_type === "coding_comparison",
          )
          .map((f) => ({
            id: String(f.id),
            name: f.display_name || f.schema_name || String(f.id),
            display_name: f.display_name,
            description: f.description || null,
            metadata: { schema: f.schema_name, file: f },
            source: "project",
          }));
        setAvailableCodedData(codingFiles);
        // Do not auto-select; require the user to pick a coded data file.
        // If caller provided a preselected coded data via location.state, respect it.
        const pre = location?.state?.selectedCodedData;
        if (pre) {
          const match = codingFiles.find((it) => it.id === pre);
          if (match) {
            setSelectedCodedData(match.id);
            setSelectedCodedDataName(
              match?.display_name || match?.name || match?.id || "",
            );
          }
        }
        return;
      }

      // Prefer user-owned coded projects from Postgres
      const resp = await apiFetch("/api/my-files/?file_type=coding");
      if (resp.ok) {
        const json = await resp.json();
        const projects = json.projects || [];
        // map to the shape SelectionList expects
        const items = projects.map((p) => ({
          id: p.schema_name || p.id,
          name: p.display_name || p.schema_name || p.id,
          display_name: p.display_name,
          description: p.description || null,
          metadata: { schema: p.schema_name },
          source: "project",
        }));
        setAvailableCodedData(items);
        // Do not auto-select; only respect an explicit preselection via location.state
        if (items.length > 0) {
          const pre = location?.state?.selectedCodedData;
          if (pre) {
            const match = items.find((it) => it.id === pre);
            if (match) {
              setSelectedCodedData(match.id);
              setSelectedCodedDataName(
                match?.display_name || match?.name || match?.id || "",
              );
            }
          }
        }
        return;
      }

      // If project-backed listing fails, expose empty list (no filesystem fallback)
      console.warn("Failed to fetch coded data list; no coded data available");
      setAvailableCodedData([]);
      setSelectedCodedData(null);
      setSelectedCodedDataName("");
    } catch (err) {
      console.error("Error fetching coded data list:", err);
    }
  };

  useEffect(() => {
    fetchAvailableCodedData();
    fetchProjects();
  }, []);

  // Refresh available coded data when project selection or projects list changes
  useEffect(() => {
    fetchAvailableCodedData();
  }, [selectedProject, projectsList]);

  const fetchProjects = async () => {
    try {
      const resp = await apiFetch("/api/projects/");
      if (!resp.ok) return;
      const data = await resp.json();
      const projects = data.projects || [];
      setProjectsList(projects);
      // Default to 'All Projects' (no project selected)
      if (!selectedProject) setSelectedProject("");
    } catch (e) {
      console.error("Error fetching projects:", e);
    }
  };

  const handleCodedDataChange = (codedDataId) => {
    setSelectedCodedData(codedDataId);
    const sel = availableCodedData.find((cd) => cd.id === codedDataId);
    setSelectedCodedDataName(sel?.display_name || sel?.name || codedDataId);
  };

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
            {(projectsList || []).map((p) => (
              <option key={p.id} value={String(p.id)}>
                {p.projectname || p.display_name || p.id}
              </option>
            ))}
          </select>
        </div>
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
          {selectedCodedData ? (
            <MarkdownView
              key={
                selectedCodedData
                  ? `${selectedCodedData}-${refreshKey}`
                  : `none-${refreshKey}`
              }
              selectedId={selectedCodedData}
              title={selectedCodedDataName}
              description={
                availableCodedData.find((cd) => cd.id === selectedCodedData)
                  ?.description
              }
              fetchStyle="query"
              fetchBase="/api/coded-data"
              queryParamName="coded_id"
              saveUrl={"/api/save-file-coded-data/"}
              saveIdFieldName={"schema_name"}
              saveAsProject={true}
              projectSchema={selectedCodedData}
              onSaved={(resp) => {
                if (typeof resp === "string") {
                  if (resp !== selectedCodedData) {
                    setSelectedCodedData(resp);
                    fetchAvailableCodedData();
                  }
                } else if (resp && resp.display_name) {
                  setSelectedCodedDataName(resp.display_name);
                  fetchAvailableCodedData();
                }
                // force remount/refresh of MarkdownView to reload content
                setRefreshKey((k) => k + 1);
              }}
              emptyLabel="View Coding"
            />
          ) : (
            <div style={{ color: "#888", padding: 20 }}>
              Select a coded data file to view
            </div>
          )}
        </div>
      </div>
    </>
  );
}
