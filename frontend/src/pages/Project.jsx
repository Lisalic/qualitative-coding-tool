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
                <p>Show database tables and stats for this project.</p>
              </div>
            )}

            {activeTab === "filtered" && (
              <div>
                <h2>Filtered Database</h2>
                <p>
                  Tools and views for filtered datasets related to this project.
                </p>
              </div>
            )}

            {activeTab === "codebook" && (
              <div>
                <h2>Codebook</h2>
                <p>Generate and view codebooks for this project.</p>
              </div>
            )}

            {activeTab === "coding" && (
              <div>
                <h2>Coding</h2>
                <p>Views for applying and reviewing coding for this project.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
