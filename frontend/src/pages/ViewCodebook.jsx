import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { apiFetch } from "../api";
import "../styles/Data.css";
import "../styles/DataTable.css";
import MarkdownView from "../components/codebook/MarkdownView";
import CodebookTree from "../components/codebook/CodebookTree";
import SelectionList from "../components/shared/SelectionList";

export default function ViewCodebook() {
  const navigate = useNavigate();
  const location = useLocation();
  const [availableCodebooks, setAvailableCodebooks] = useState([]);
  const [selectedCodebook, setSelectedCodebook] = useState(null);
  const [projectsList, setProjectsList] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [codebookContent, setCodebookContent] = useState("");
  const [selectedCodebookName, setSelectedCodebookName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState("markdown");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [userPrompt, setUserPrompt] = useState("");

  const fetchAvailableCodebooks = async () => {
    try {
      // Prefer project-backed files when a project is selected
      if (projectsList && projectsList.length > 0 && selectedProject) {
        const projectObj = projectsList.find(
          (p) => String(p.id) === String(selectedProject),
        );
        const files = (projectObj && projectObj.files) || [];
        const codebookFiles = files
          .filter(
            (f) =>
              f.file_type === "codebook" ||
              f.file_type === "codebook_comparison",
          )
          .map((f) => ({
            id: String(f.id),
            display_name: f.display_name || f.schema_name || String(f.id),
            description: f.description || null,
            metadata: { schema: f.schema_name, file: f },
          }));
        setAvailableCodebooks(codebookFiles);
        // If navigation provided a preselected codebook (from Project view), respect it
        const pre = location?.state?.selected;
        if (pre) {
          const match = codebookFiles.find(
            (it) =>
              String(it.id) === String(pre) ||
              it.metadata?.schema === pre ||
              it.display_name === pre,
          );
          if (match) {
            setSelectedCodebook(match.id);
            setSelectedCodebookName(
              match.display_name || match.name || match.id || "",
            );
          }
        }
        // otherwise do not auto-select; require the user to click one
        return;
      }

      const response = await apiFetch("/api/list-codebooks");
      if (!response.ok) {
        throw new Error("Failed to fetch codebooks list");
      }
      const data = await response.json();
      setAvailableCodebooks(data.codebooks);
      if (data.codebooks.length > 0) {
        // Respect navigation state.selected (e.g., from Project view)
        const preNav = location?.state?.selected;
        if (
          preNav &&
          data.codebooks.some((cb) => String(cb.id) === String(preNav))
        ) {
          setSelectedCodebook(String(preNav));
          const sel = data.codebooks.find(
            (cb) => String(cb.id) === String(preNav),
          );
          setSelectedCodebookName(
            sel?.display_name || sel?.name || sel?.id || "",
          );
          // leave early — respect explicit navigation selection
          return;
        }

        const urlParams = new URLSearchParams(window.location.search);
        const selectedFromUrl = urlParams.get("selected");
        if (
          selectedFromUrl &&
          data.codebooks.some((cb) => String(cb.id) === String(selectedFromUrl))
        ) {
          setSelectedCodebook(selectedFromUrl);
          const sel = data.codebooks.find(
            (cb) => String(cb.id) === String(selectedFromUrl),
          );
          setSelectedCodebookName(
            sel?.display_name || sel?.name || sel?.id || "",
          );
        }
        // otherwise leave nothing selected until the user chooses
      }
    } catch (err) {
      console.error("Error fetching codebooks list:", err);
    }
  };

  const fetchCodebook = async (codebookId) => {
    try {
      setLoading(true);
      setError(null);

      const response = await apiFetch(
        `/api/codebook?codebook_id=${codebookId}`,
      );
      if (!response.ok) {
        throw new Error("Failed to fetch codebook");
      }
      const data = await response.json();
      if (data.codebook) {
        setCodebookContent(data.codebook);
        setSystemPrompt(data.systemprompt || "");
        setUserPrompt(data.userprompt || "");
      } else {
        setCodebookContent("");
        setSystemPrompt("");
        setUserPrompt("");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAvailableCodebooks();
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const resp = await apiFetch("/api/projects/");
      if (!resp.ok) return;
      const data = await resp.json();
      const projects = data.projects || [];
      setProjectsList(projects);
    } catch (e) {
      console.error("Error fetching projects:", e);
    }
  };

  useEffect(() => {
    if (selectedCodebook) {
      fetchCodebook(selectedCodebook);
      const sel = availableCodebooks.find(
        (cb) => String(cb.id) === String(selectedCodebook),
      );
      setSelectedCodebookName(sel?.display_name || sel?.name || sel?.id || "");
    }
  }, [selectedCodebook, availableCodebooks]);

  useEffect(() => {
    // when project selection changes, refresh available codebooks
    fetchAvailableCodebooks();
  }, [selectedProject, projectsList]);

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
          items={availableCodebooks}
          selectedId={selectedCodebook}
          onSelect={(id) => setSelectedCodebook(id)}
          className="codebook-selector"
          buttonClass="db-button"
          emptyMessage="No codebooks available"
        />
        <div
          style={{
            border: "1px solid #ffffff",
            borderRadius: "8px",
            padding: "20px",
            backgroundColor: "#000000",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: 8,
              marginBottom: 12,
            }}
          >
            <button
              onClick={() => setViewMode("markdown")}
              disabled={viewMode === "markdown"}
              className="view-button"
              style={{
                padding: "8px 16px",
                fontSize: "14px",
                cursor: viewMode === "markdown" ? "default" : "pointer",
              }}
            >
              Show Text
            </button>
            <button
              onClick={() => setViewMode("tree")}
              disabled={viewMode === "tree"}
              className="view-button"
              style={{
                padding: "8px 16px",
                fontSize: "14px",
                cursor: viewMode === "tree" ? "default" : "pointer",
              }}
            >
              Show Tree
            </button>
          </div>

          {viewMode === "markdown" ? (
            selectedCodebook ? (
              (() => {
                const selObj = availableCodebooks.find(
                  (cb) => cb.id === selectedCodebook,
                );
                const projectSchema =
                  selObj?.metadata?.schema ||
                  selObj?.schema_name ||
                  selObj?.id ||
                  null;
                return (
                  <MarkdownView
                    selectedId={selectedCodebook}
                    title={selectedCodebookName}
                    description={selObj?.description}
                    fetchStyle="query"
                    fetchBase="/api/codebook"
                    queryParamName="codebook_id"
                    saveUrl={"/api/save-file-codebook/"}
                    saveIdFieldName={"schema_name"}
                    saveAsProject={true}
                    projectSchema={projectSchema}
                    systemPrompt={systemPrompt}
                    userPrompt={userPrompt}
                    onSaved={(resp) => {
                      if (typeof resp === "string") {
                        if (resp !== selectedCodebook) {
                          setSelectedCodebook(resp);
                          fetchAvailableCodebooks();
                        }
                      } else if (resp && resp.display_name) {
                        setSelectedCodebookName(resp.display_name);
                        fetchAvailableCodebooks();
                      }
                    }}
                    emptyLabel="View Codebook"
                  />
                );
              })()
            ) : (
              <div style={{ color: "#888", padding: 20 }}>
                Select a codebook file to view
              </div>
            )
          ) : selectedCodebook ? (
            <CodebookTree
              codebookId={selectedCodebook}
              codebookName={selectedCodebookName}
            />
          ) : null}
          {!codebookContent && !loading && !error && (
            <p>No codebook selected or found. Generate a codebook first.</p>
          )}
          {/* (Tree is shown when 'Show Tree' is selected above) */}
        </div>
      </div>
    </>
  );
}
