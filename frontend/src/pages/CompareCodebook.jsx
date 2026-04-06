import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch } from "../api";
import CompareDualSelectPanel from "../components/compare/CompareDualSelectPanel";
import CompareModelPromptPanel from "../components/compare/CompareModelPromptPanel";
import CompareResultPanel from "../components/compare/CompareResultPanel";
import "../styles/Home.css";

const EXAMPLE_PROMPT =
  "Please provide a detailed comparison focusing on:\n- Key differences in coding approaches\n- Overlapping themes and codes\n- Unique insights from each codebook\n- Recommendations for merging or refining the codebooks";

export default function CompareCodebook() {
  const location = useLocation();
  const [codebooks, setCodebooks] = useState([]);
  const [a, setA] = useState(location.state?.codebookA || "");
  const [b, setB] = useState("");
  const [loading, setLoading] = useState(false);
  const [comparison, setComparison] = useState("");
  const [error, setError] = useState("");
  const [model, setModel] = useState("");
  const [projects, setProjects] = useState([]);
  const [additionalPrompt, setAdditionalPrompt] = useState("");

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
    if (!a || !b) return setError("Select two codebooks to compare");
    const apiKey = localStorage.getItem("apiKey");
    if (!apiKey) return setError("Set your API key in the navbar first");

    const form = new FormData();
    form.append("codebook_a", a);
    form.append("codebook_b", b);
    form.append("api_key", apiKey);
    if (model) form.append("model", model);
    if (additionalPrompt.trim()) form.append("prompt", additionalPrompt.trim());

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
      <div className="compare-page">
        <h1 className="tool-page-title">Compare Codebook</h1>

        <form onSubmit={submitCompare}>
          <div className="compare-layout-row">
            <CompareDualSelectPanel
              panelTitle="Select codebooks"
              labelA="Codebook A"
              labelB="Codebook B"
              placeholderOption="Select a codebook"
              options={codebooks}
              valueA={a}
              valueB={b}
              onChangeA={setA}
              onChangeB={setB}
            />

            <CompareModelPromptPanel
              model={model}
              onModelChange={setModel}
              additionalPrompt={additionalPrompt}
              onAdditionalPromptChange={setAdditionalPrompt}
              examplePromptText={EXAMPLE_PROMPT}
            />
          </div>

          <div className="compare-actions-bar">
            <button
              className="project-tab compare-submit-btn"
              type="submit"
              disabled={loading}
            >
              {loading ? "Comparing..." : "Compare"}
            </button>
          </div>
        </form>

        {error && (
          <div className="alert alert--error compare-page-alert">{error}</div>
        )}

        <CompareResultPanel
          comparison={comparison}
          fileType="codebook_comparison"
          valueA={a}
          valueB={b}
          options={codebooks}
          projects={projects}
        />
      </div>
    </div>
  );
}
