import { useParams, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { apiFetch } from "../api";
import "../styles/Home.css";

export default function Project() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("database");

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    apiFetch("/api/projects/")
      .then((r) => r.json())
      .then((data) => {
        if (!mounted) return;
        const rows = data.projects || [];
        const found = rows.find((p) => String(p.id) === String(projectId));
        setProject(found || null);
        setLoading(false);
      })
      .catch(() => {
        if (!mounted) return;
        setProject(null);
        setLoading(false);
      });
    return () => (mounted = false);
  }, [projectId]);

  if (loading) return <div style={{ padding: 20 }}>Loading project...</div>;
  if (!project) return <div style={{ padding: 20 }}>Project not found</div>;

  // determine files for categories
  const dbFile =
    (project.files || []).find((f) => f.file_type === "raw_data") || null;
  const filteredFile =
    (project.files || []).find((f) => f.file_type === "filtered_data") || null;
  const codebookFile =
    (project.files || []).find((f) => f.file_type === "codebook") || null;
  const codingFile =
    (project.files || []).find((f) => f.file_type === "coding") || null;

  return (
    <div className="home-container">
      <div className="form-wrapper">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <h1>{project.projectname}</h1>
            <div style={{ color: "#666" }}>{project.description}</div>
          </div>
          <div />
        </div>

        <div style={{ marginTop: 16 }}>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              className={`project-tab ${activeTab === "database" ? "selected" : ""}`}
              onClick={(e) => {
                e.stopPropagation();
                setActiveTab("database");
              }}
            >
              Database
            </button>
            <button
              type="button"
              className={`project-tab ${activeTab === "filtered" ? "selected" : ""}`}
              onClick={(e) => {
                e.stopPropagation();
                setActiveTab("filtered");
              }}
            >
              Filtered Database
            </button>
            <button
              type="button"
              className={`project-tab ${activeTab === "codebook" ? "selected" : ""}`}
              onClick={(e) => {
                e.stopPropagation();
                setActiveTab("codebook");
              }}
            >
              Codebook
            </button>
            <button
              type="button"
              className={`project-tab ${activeTab === "coding" ? "selected" : ""}`}
              onClick={(e) => {
                e.stopPropagation();
                setActiveTab("coding");
              }}
            >
              Coding
            </button>
          </div>

          <div style={{ marginTop: 16 }}>
            {activeTab === "database" && (
              <div>
                <h2>Database</h2>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    {dbFile
                      ? dbFile.display_name || dbFile.schema_name
                      : "No database"}
                  </div>
                  {dbFile && (
                    <button
                      className="main-button"
                      onClick={() =>
                        navigate("/data", {
                          state: { selectedDatabase: dbFile.schema_name },
                        })
                      }
                      type="button"
                    >
                      View
                    </button>
                  )}
                </div>
              </div>
            )}

            {activeTab === "filtered" && (
              <div>
                <h2>Filtered Database</h2>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    {filteredFile
                      ? filteredFile.display_name || filteredFile.schema_name
                      : "No filtered database"}
                  </div>
                  {filteredFile && (
                    <button
                      className="main-button"
                      onClick={() =>
                        navigate("/filtered-data", {
                          state: { selectedDatabase: filteredFile.schema_name },
                        })
                      }
                      type="button"
                    >
                      View
                    </button>
                  )}
                </div>
              </div>
            )}

            {activeTab === "codebook" && (
              <div>
                <h2>Codebook</h2>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    {codebookFile
                      ? codebookFile.display_name || codebookFile.schema_name
                      : "No codebook"}
                  </div>
                  {codebookFile && (
                    <button
                      className="main-button"
                      onClick={() =>
                        navigate(
                          `/codebook-view?selected=${encodeURIComponent(codebookFile.schema_name || codebookFile.display_name || codebookFile.id)}`,
                        )
                      }
                      type="button"
                    >
                      View
                    </button>
                  )}
                </div>
              </div>
            )}

            {activeTab === "coding" && (
              <div>
                <h2>Coding</h2>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    {codingFile
                      ? codingFile.display_name || codingFile.schema_name
                      : "No coding"}
                  </div>
                  {codingFile && (
                    <button
                      className="main-button"
                      onClick={() =>
                        navigate("/coding-view", {
                          state: { selectedCodedData: codingFile.schema_name },
                        })
                      }
                      type="button"
                    >
                      View
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
