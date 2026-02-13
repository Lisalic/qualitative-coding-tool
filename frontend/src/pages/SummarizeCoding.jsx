import React, { useEffect, useState } from "react";
import { apiFetch } from "../api";
import ReactMarkdown from "react-markdown";
import { AI_MODELS } from "../lib/constants";
import "../styles/Home.css";

export default function SummarizeCoding() {
  const [codings, setCodings] = useState([]);
  const [selectedCoding, setSelectedCoding] = useState("");
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState("");
  const [additionalPrompt, setAdditionalPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState("");
  const [error, setError] = useState("");
  const [model, setModel] = useState("tngtech/deepseek-r1t2-chimera:free");

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
        setCodings(list);
        if (list.length > 0) {
          setSelectedCoding(list[0].value);
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

  const submitSummarize = async (ev) => {
    ev.preventDefault();
    setSummary("");
    setError("");
    if (!selectedCoding) return setError("Select a coding to summarize");
    const apiKey = localStorage.getItem("apiKey");
    if (!apiKey) return setError("Set your API key in the navbar first");

    const form = new FormData();
    form.append("coding", selectedCoding);
    form.append("api_key", apiKey);
    if (model) form.append("model", model);
    if (additionalPrompt.trim()) form.append("prompt", additionalPrompt.trim());
    if (selectedProject) form.append("project_id", selectedProject);

    try {
      setLoading(true);
      const resp = await apiFetch("/api/summarize-coding/", {
        method: "POST",
        body: form,
      });
      if (!resp.ok) {
        const d = await resp.json().catch(() => ({}));
        throw new Error(d.error || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      if (data.error) setError(data.error);
      else setSummary(data.summary || "");
    } catch (err) {
      setError(String(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="home-container">
      <div style={{ width: "100%", maxWidth: 1400, padding: 20 }}>
        <form onSubmit={submitSummarize}>
          <div className="compare-panel">
            <div className="panel-title">Summarize Coding</div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", marginBottom: 6 }}>
                Coding
              </label>
              <select
                className="form-input"
                value={selectedCoding}
                onChange={(e) => setSelectedCoding(e.target.value)}
              >
                <option value="">-- select --</option>
                {codings.map((coding) => (
                  <option key={coding.value} value={coding.value}>
                    {coding.label}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", marginBottom: 6 }}>Model</label>
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

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", marginBottom: 6 }}>
                Prompt
              </label>
              <textarea
                value={additionalPrompt}
                onChange={(e) => setAdditionalPrompt(e.target.value)}
                placeholder="Enter any specific instructions for the summary..."
                style={{
                  width: "100%",
                  minHeight: 80,
                  padding: 12,
                  backgroundColor: "#1a1a1a",
                  color: "#fff",
                  border: "1px solid #555",
                  borderRadius: 4,
                  fontFamily: "inherit",
                  resize: "vertical",
                  fontSize: "14px",
                }}
              />
            </div>

            <div
              className="compare-actions"
              style={{ justifyContent: "center" }}
            >
              <button className="project-tab" type="submit" disabled={loading}>
                {loading ? "Summarizing..." : "Summarize"}
              </button>
            </div>
          </div>
        </form>

        {error && <div style={{ color: "#f44", marginTop: 10 }}>{error}</div>}

        {summary !== "" && (
          <div style={{ marginTop: 16 }}>
            <h3 style={{ margin: 0 }}>Summary Result</h3>
            <div
              style={{
                marginTop: 8,
                padding: 16,
                backgroundColor: "#1a1a1a",
                border: "1px solid #555",
                borderRadius: 8,
                maxHeight: 600,
                overflow: "auto",
                whiteSpace: "pre-wrap",
                fontFamily: "monospace",
                fontSize: "14px",
                lineHeight: 1.5,
              }}
            >
              <ReactMarkdown>{summary}</ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
