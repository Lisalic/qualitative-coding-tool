import React, { useEffect, useState } from "react";
import { apiFetch } from "../api";
import ReactMarkdown from "react-markdown";
import AiModelFormGroup from "../components/models/AiModelFormGroup";
import AiLabel from "../components/forms/AiLabel";
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
  const [saveName, setSaveName] = useState("");
  const [saveDescription, setSaveDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState("");
  const [saveError, setSaveError] = useState("");
  // No default model: require explicit user selection
  const [model, setModel] = useState("");

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

  const saveSummaryToProject = async (ev) => {
    ev?.preventDefault();
    setSaveError("");
    setSaveSuccess("");
    if (!saveName || !saveName.trim())
      return setSaveError("Provide a name for the summary");
    if (!selectedProject)
      return setSaveError("Select a project to attach the summary to");

    try {
      setSaving(true);
      const form = new FormData();
      form.append("content", summary || "");
      form.append("name", saveName.trim());
      form.append("description", saveDescription || "");
      form.append("project_id", String(selectedProject));

      const resp = await apiFetch("/api/save-summary/", {
        method: "POST",
        body: form,
      });
      if (!resp.ok) {
        const d = await resp.json().catch(() => ({}));
        throw new Error(d.detail || d.error || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      setSaveSuccess("Saved summary to project");
      // Optionally reset fields
      setSaveName("");
      setSaveDescription("");
    } catch (err) {
      setSaveError(String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="home-container">
      <div style={{ width: "100%", maxWidth: 1400, padding: 20 }}>
        <form onSubmit={submitSummarize}>
          <div className="compare-panel">
            <div className="panel-title">Summarize Coding</div>

            <div
              style={{
                display: "flex",
                gap: 16,
                alignItems: "flex-start",
                marginBottom: 16,
              }}
            >
              <div style={{ flex: 1 }}>
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

              <div style={{ width: 188, minWidth: 188 }}>
                <AiModelFormGroup
                  className=""
                  label="Model"
                  labelStyle={{ display: "block", marginBottom: 6 }}
                  model={model}
                  onModelChange={setModel}
                  selectPlaceholder="dash"
                />
              </div>
            </div>

            <div style={{ marginBottom: 16 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  marginBottom: 6,
                }}
              >
                <AiLabel text="Prompt" style={{ marginBottom: 0 }} />
                <button
                  className="project-tab"
                  type="button"
                  onClick={() =>
                    setAdditionalPrompt(
                      "Please provide a comprehensive summary focusing on:\n- Key themes and patterns in the coded data\n- Most frequently applied codes and their significance\n- Relationships between different codes\n- Representative examples from the data\n- Overall insights and implications",
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
                placeholder="Enter any specific instructions for the summary..."
                style={{
                  width: "100%",
                  minHeight: 80,
                  padding: 12,
                  backgroundColor: "#1a1a1a",
                  color: "#fff",
                  border: "1px solid #ffffff",
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
                backgroundColor: "#000000",
                border: "1px solid #ffffff",
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

            <div
              style={{
                marginTop: 12,
                padding: 12,
                background: "#000000",
                border: "2px solid #ffffff",
                borderRadius: 8,
                boxShadow: "0 4px 6px rgba(255, 255, 255, 0.1)",
              }}
            >
              <h4 style={{ margin: "0 0 8px 0" }}>Save Summary</h4>
              <div style={{ display: "flex", gap: 12, marginBottom: 8 }}>
                <div style={{ flex: 1 }}>
                  <label style={{ display: "block", marginBottom: 6 }}>
                    Project
                  </label>
                  <select
                    className="form-input"
                    value={selectedProject}
                    onChange={(e) => setSelectedProject(e.target.value)}
                  >
                    <option value="">-- select project --</option>
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.projectname}
                      </option>
                    ))}
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ display: "block", marginBottom: 6 }}>
                    Name
                  </label>
                  <input
                    className="form-input"
                    value={saveName}
                    onChange={(e) => setSaveName(e.target.value)}
                    placeholder="Summary name"
                  />
                </div>
              </div>
              <div style={{ marginBottom: 8 }}>
                <label style={{ display: "block", marginBottom: 6 }}>
                  Description (optional)
                </label>
                <input
                  className="form-input"
                  value={saveDescription}
                  onChange={(e) => setSaveDescription(e.target.value)}
                  placeholder="Short description"
                />
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className="project-tab"
                  onClick={saveSummaryToProject}
                  disabled={saving}
                >
                  {saving ? "Saving..." : "Save Summary to Project"}
                </button>
                {saveSuccess && (
                  <div style={{ color: "#4CAF50", alignSelf: "center" }}>
                    {saveSuccess}
                  </div>
                )}
                {saveError && (
                  <div style={{ color: "#ff6b6b", alignSelf: "center" }}>
                    {saveError}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
