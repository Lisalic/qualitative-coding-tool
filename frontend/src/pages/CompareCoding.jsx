import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch } from "../api";
import ReactMarkdown from "react-markdown";
import { AI_MODELS } from "../lib/constants";
import "../styles/Home.css";

export default function CompareCoding() {
  const location = useLocation();
  const [items, setItems] = useState([]);
  const [a, setA] = useState(location.state?.codingA || "");
  const [b, setB] = useState("");
  const [loading, setLoading] = useState(false);
  const [comparison, setComparison] = useState("");
  const [error, setError] = useState("");
  // No default model: require explicit user selection
  const [model, setModel] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [additionalPrompt, setAdditionalPrompt] = useState("");

  useEffect(() => {
    let mounted = true;
    apiFetch("/api/my-files/?file_type=coding")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!mounted || !data) return;
        const list = (data.projects || []).map((p) => ({
          value: p.schema_name,
          label: p.display_name || p.schema_name,
        }));
        setItems(list);
        if (a) {
          // If coding A is pre-selected (via navigation state), optionally set a default for B
          const availableForB = list.filter((item) => item.value !== a);
          if (availableForB.length > 0 && !b) {
            setB(availableForB[0].value);
          }
        }
      })
      .catch(() => {});
    return () => (mounted = false);
  }, []);

  useEffect(() => {
    let mounted = true;
    apiFetch("/api/projects/")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!mounted || !data) return;
        const list = Array.isArray(data.projects) ? data.projects : [];
        setProjects(list);
      })
      .catch(() => {});
    return () => (mounted = false);
  }, []);

  const submitCompare = async (ev) => {
    ev.preventDefault();
    setComparison("");
    setError("");
    if (!a || !b) return setError("Select two codings to compare");
    const apiKey = localStorage.getItem("apiKey");
    if (!apiKey) return setError("Set your API key in the navbar first");

    const form = new FormData();
    form.append("coding_a", a);
    form.append("coding_b", b);
    form.append("api_key", apiKey);
    if (model) form.append("model", model);
    if (additionalPrompt.trim()) form.append("prompt", additionalPrompt.trim());

    try {
      setLoading(true);
      const resp = await apiFetch("/api/compare-codings/", {
        method: "POST",
        body: form,
      });
      if (!resp.ok) {
        const d = await resp.json().catch(() => ({}));
        throw new Error(d.error || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      if (data.error) setError(data.error);
      else setComparison(data.comparison || "");
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="home-container">
      <div style={{ width: "100%", maxWidth: 1200, padding: 20 }}>
        <h1 style={{ textAlign: "center", marginBottom: 24 }}>Compare Coding</h1>

        <form onSubmit={submitCompare}>
          <div className="compare-layout-row">
            <div className="compare-layout-column">
              <div className="compare-panel-card">
                <div className="compare-panel-header">
                  <h2 className="compare-panel-title">Select codings</h2>
                </div>
                <div className="compare-form-group">
                  <label className="compare-label">Coding A</label>
                  <select
                    className="form-input"
                    value={a}
                    onChange={(e) => setA(e.target.value)}
                  >
                    <option value="">Select a coding</option>
                    {items.map((it) => (
                      <option key={it.value} value={it.value}>
                        {it.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="compare-form-group">
                  <label className="compare-label">Coding B</label>
                  <select
                    className="form-input"
                    value={b}
                    onChange={(e) => setB(e.target.value)}
                  >
                    <option value="">Select a coding</option>
                    {items.map((it) => (
                      <option key={it.value} value={it.value}>
                        {it.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="compare-layout-column">
              <div className="compare-panel-card">
                <div className="compare-panel-header">
                  <h2 className="compare-panel-title">Model & instructions</h2>
                </div>

                <div className="compare-form-group compare-model-select">
                  <label className="compare-label">Model</label>
                  <select
                    className="form-input form-input-model"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                  >
                    <option value="">Select a model</option>
                    {AI_MODELS.map((modelOption) => (
                      <option
                        key={modelOption.value}
                        value={modelOption.value}
                      >
                        {modelOption.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="compare-form-group">
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      marginBottom: 4,
                    }}
                  >
                    <label className="compare-label">Prompt (optional)</label>
                    <button
                      className="project-tab prompt-example-btn"
                      type="button"
                      onClick={() =>
                        setAdditionalPrompt(
                          "Please provide a detailed comparison focusing on:\n- Differences in coding decisions and interpretations\n- Patterns of agreement and disagreement\n- Quality and consistency of coding applications\n- Recommendations for improving coding reliability",
                        )
                      }
                    >
                      Load Example Prompt
                    </button>
                  </div>
                  <textarea
                    value={additionalPrompt}
                    onChange={(e) => setAdditionalPrompt(e.target.value)}
                    placeholder="Enter any specific instructions for the comparison..."
                    className="compare-textarea"
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="compare-actions-bar">
            <button
              className="project-tab"
              type="submit"
              disabled={loading}
              style={{
                padding: "10px 28px",
                fontSize: "16px",
                borderWidth: 2,
              }}
            >
              {loading ? "Comparing..." : "Compare"}
            </button>
          </div>
        </form>

        {error && (
          <div className="alert alert--error" style={{ marginTop: 16 }}>
            {error}
          </div>
        )}

        {comparison !== "" && (
          <div className="compare-layout-column compare-layout-column--results">
            <div className="compare-panel-card">
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 12,
                }}
              >
                <h2 className="compare-panel-title">Comparison result</h2>
                <div style={{ display: "flex", gap: 8 }}>
                  <button
                    className="project-tab"
                    onClick={() => {
                      if (navigator.clipboard && comparison) {
                        navigator.clipboard.writeText(comparison).catch(() => {});
                      }
                    }}
                  >
                    Copy
                  </button>
                  <button
                    className="project-tab"
                    onClick={async () => {
                      setSaveMessage("");
                      const labelA =
                        (items.find((it) => it.value === a) || {}).label || a;
                      const labelB =
                        (items.find((it) => it.value === b) || {}).label || b;
                      const title = `Comparison: ${labelA} vs ${labelB}`;
                      const description = `Compared ${labelA} and ${labelB}`;
                      const form = new FormData();
                      form.append("content", comparison);
                      form.append("title", title);
                      form.append("description", description);
                      form.append("file_type", "coding_comparison");
                      if (selectedProject)
                        form.append("project_id", String(selectedProject));
                      try {
                        setSaving(true);
                        const resp = await apiFetch("/api/save-comparison/", {
                          method: "POST",
                          body: form,
                        });
                        if (!resp.ok) {
                          const d = await resp.json().catch(() => ({}));
                          throw new Error(d.detail || `HTTP ${resp.status}`);
                        }
                        const d = await resp.json();
                        setSaveMessage(d.message || "Saved");
                      } catch (err) {
                        setSaveMessage(String(err));
                      } finally {
                        setSaving(false);
                      }
                    }}
                    disabled={saving}
                  >
                    {saving ? "Saving..." : "Save"}
                  </button>
                </div>
              </div>

              {projects.length > 0 && (
                <div style={{ marginBottom: 8 }}>
                  <label style={{ color: "#ccc", marginRight: 8 }}>
                    Save to project:
                  </label>
                  <select
                    className="form-input"
                    value={selectedProject}
                    onChange={(e) => setSelectedProject(e.target.value)}
                  >
                    <option value="">Select a project</option>
                    {projects.map((pr) => (
                      <option key={pr.id} value={pr.id}>
                        {pr.projectname}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {saveMessage && (
                <div style={{ marginBottom: 8, color: "#ccffcc" }}>
                  {saveMessage}
                </div>
              )}
              <div className="comparison-output">
                <ReactMarkdown>{comparison}</ReactMarkdown>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
