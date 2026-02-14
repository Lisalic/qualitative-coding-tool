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
  const [model, setModel] = useState("tngtech/deepseek-r1t2-chimera:free");
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
          // If coding A is pre-selected, set B to the first available coding that's different
          const availableForB = list.filter((item) => item.value !== a);
          if (availableForB.length > 0) {
            setB(availableForB[0].value);
          }
        } else if (list.length >= 2) {
          setA(list[0].value);
          setB(list[1].value);
        } else if (list.length === 1) {
          setA(list[0].value);
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
        if (list.length > 0) setSelectedProject(list[0].id || "");
      })
      .catch(() => {});
    return () => (mounted = false);
  }, []);

  const swap = () => {
    setA(b);
    setB(a);
  };

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
      <div style={{ width: "100%", maxWidth: 1400, padding: 20 }}>
        <h1 style={{ textAlign: "center" }}>Compare Coding</h1>

        <form onSubmit={submitCompare}>
          <div className="compare-wrap" style={{ flexDirection: "column" }}>
            <div style={{ flex: 1 }}>
              <div className="compare-grid">
                <div className="compare-card">
                  <div className="compare-toolbar">Coding A</div>
                  <select
                    className="form-input"
                    value={a}
                    onChange={(e) => setA(e.target.value)}
                  >
                    <option value="">-- select --</option>
                    {items.map((it) => (
                      <option key={it.value} value={it.value}>
                        {it.label}
                      </option>
                    ))}
                  </select>
                </div>

                <div
                  style={{
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                  }}
                >
                  <button
                    type="button"
                    className="swap-btn"
                    onClick={swap}
                    title="Swap selections"
                  >
                    ⇆
                  </button>
                </div>

                <div className="compare-card">
                  <div className="compare-toolbar">Coding B</div>
                  <select
                    className="form-input"
                    value={b}
                    onChange={(e) => setB(e.target.value)}
                  >
                    <option value="">-- select --</option>
                    {items.map((it) => (
                      <option key={it.value} value={it.value}>
                        {it.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="compare-panel" style={{ marginTop: 20 }}>
              <div>
                <label style={{ display: "block", marginBottom: 6 }}>
                  Model
                </label>
                <select
                  className="form-input"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                >
                  {AI_MODELS.map((modelOption) => (
                    <option key={modelOption.value} value={modelOption.value}>
                      {modelOption.label}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ marginTop: 12 }}>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    marginBottom: 6,
                  }}
                >
                  <label style={{ marginBottom: 0 }}>Prompt</label>
                  <button
                    className="project-tab"
                    type="button"
                    onClick={() =>
                      setAdditionalPrompt(
                        "Please provide a detailed comparison focusing on:\n- Differences in coding decisions and interpretations\n- Patterns of agreement and disagreement\n- Quality and consistency of coding applications\n- Recommendations for improving coding reliability",
                      )
                    }
                    style={{
                      fontSize: "12px",
                      padding: "4px 8px",
                      flexShrink: 0,
                    }}
                  >
                    Load Example Prompt
                  </button>
                </div>
                <textarea
                  value={additionalPrompt}
                  onChange={(e) => setAdditionalPrompt(e.target.value)}
                  placeholder="Enter any specific instructions for the comparison..."
                  style={{
                    width: "100%",
                    minHeight: 80,
                    padding: 8,
                    backgroundColor: "#1a1a1a",
                    color: "#fff",
                    border: "1px solid #555",
                    borderRadius: 4,
                    fontFamily: "inherit",
                    resize: "vertical",
                  }}
                />
              </div>

              <div style={{ marginTop: 6 }} className="compare-actions">
                <button
                  className="project-tab"
                  type="submit"
                  disabled={loading}
                >
                  {loading ? "Comparing..." : "Compare"}
                </button>
              </div>
            </div>
          </div>
        </form>

        {error && <div style={{ color: "#f44", marginTop: 10 }}>{error}</div>}

        {comparison !== "" && (
          <div style={{ marginTop: 16 }}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <h3 style={{ margin: 0 }}>Comparison Result</h3>
              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
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
              <div style={{ marginTop: 8 }}>
                <label style={{ color: "#ccc", marginRight: 8 }}>
                  Save to project:
                </label>
                <select
                  className="form-input"
                  value={selectedProject}
                  onChange={(e) => setSelectedProject(e.target.value)}
                >
                  {projects.map((pr) => (
                    <option key={pr.id} value={pr.id}>
                      {pr.projectname}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {saveMessage && (
              <div style={{ marginTop: 8, color: "#ccffcc" }}>
                {saveMessage}
              </div>
            )}
            <div className="comparison-output">
              <ReactMarkdown>{comparison}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
