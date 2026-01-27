import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch } from "../api";
import "../styles/Home.css";

export default function CompareCodebook() {
  const location = useLocation();
  const [codebooks, setCodebooks] = useState([]);
  const [a, setA] = useState(location.state?.codebookA || "");
  const [b, setB] = useState("");
  const [loading, setLoading] = useState(false);
  const [comparison, setComparison] = useState("");
  const [error, setError] = useState("");
  const [model, setModel] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");

  useEffect(() => {
    let mounted = true;
    apiFetch("/api/my-files/?file_type=codebook")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!mounted || !data) return;
        const list = (data.projects || []).map((p) => ({
          value: p.schema_name,
          label: p.display_name || p.schema_name,
        }));
        setCodebooks(list);
        if (a) {
          // If codebook A is pre-selected, set B to the first available codebook that's different
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
    if (!a || !b) return setError("Select two codebooks to compare");
    const apiKey = localStorage.getItem("apiKey");
    if (!apiKey) return setError("Set your API key in the navbar first");

    const form = new FormData();
    form.append("codebook_a", a);
    form.append("codebook_b", b);
    form.append("api_key", apiKey);
    if (model) form.append("model", model);

    try {
      setLoading(true);
      const resp = await apiFetch("/api/compare-codebooks/", {
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
      <div style={{ width: "100%", maxWidth: 1000, padding: 20 }}>
        <h1>Compare Codebook</h1>

        <form onSubmit={submitCompare}>
          <div className="compare-wrap">
            <div style={{ flex: 1 }}>
              <div className="compare-grid">
                <div className="compare-card">
                  <div className="compare-toolbar">Codebook A</div>
                  <select
                    className="select-compact"
                    value={a}
                    onChange={(e) => setA(e.target.value)}
                  >
                    <option value="">-- select --</option>
                    {codebooks.map((it) => (
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
                  <div className="compare-toolbar">Codebook B</div>
                  <select
                    className="select-compact"
                    value={b}
                    onChange={(e) => setB(e.target.value)}
                  >
                    <option value="">-- select --</option>
                    {codebooks.map((it) => (
                      <option key={it.value} value={it.value}>
                        {it.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="compare-panel">
              <div className="panel-title">Compare Options</div>
              <div>
                <label style={{ display: "block", marginBottom: 6 }}>
                  Model
                </label>
                <select
                  className="model-select"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                >
                  <option value="tngtech/deepseek-r1t2-chimera:free">
                    tngtech/deepseek-r1t2-chimera:free
                  </option>
                  <option value="google/gemini-2.0-flash-exp:free">
                    google/gemini-2.0-flash-exp:free
                  </option>
                  <option value="tngtech/deepseek-r1t-chimera:free">
                    tngtech/deepseek-r1t-chimera:free
                  </option>
                  <option value="z-ai/glm-4.5-air:free">
                    z-ai/glm-4.5-air:free
                  </option>
                  <option value="deepseek/deepseek-r1-0528:free">
                    deepseek/deepseek-r1-0528:free
                  </option>
                  <option value="tngtech/tng-r1t-chimera:free">
                    tngtech/tng-r1t-chimera:free
                  </option>
                  <option value="nvidia/nemotron-3-nano-30b-a3b:free">
                    nvidia/nemotron-3-nano-30b-a3b:free
                  </option>
                  <option value="meta-llama/llama-3.3-70b-instruct:free">
                    meta-llama/llama-3.3-70b-instruct:free
                  </option>
                  <option value="google/gemma-3-27b-it:free">
                    google/gemma-3-27b-it:free
                  </option>
                </select>
              </div>

              <div style={{ marginTop: 6 }} className="compare-actions">
                <button
                  className="project-tab"
                  type="submit"
                  disabled={loading}
                >
                  {loading ? "Comparing..." : "Compare"}
                </button>
                <button
                  className="project-tab"
                  type="button"
                  onClick={() => {
                    setComparison("");
                    setError("");
                  }}
                >
                  Clear
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
                    // Save comparison
                    setSaveMessage("");
                    const labelA =
                      (codebooks.find((it) => it.value === a) || {}).label || a;
                    const labelB =
                      (codebooks.find((it) => it.value === b) || {}).label || b;
                    const title = `Comparison: ${labelA} vs ${labelB}`;
                    const description = `Compared ${labelA} and ${labelB}`;
                    const form = new FormData();
                    form.append("content", comparison);
                    form.append("title", title);
                    form.append("description", description);
                    form.append("file_type", "codebook_comparison");
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
            <div className="comparison-output" style={{ marginTop: 8 }}>
              {comparison}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
