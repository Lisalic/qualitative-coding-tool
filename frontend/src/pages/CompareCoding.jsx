import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch } from "../api";
import CompareDualSelectPanel from "../components/compare/CompareDualSelectPanel";
import CompareModelPromptPanel from "../components/compare/CompareModelPromptPanel";
import CompareResultPanel from "../components/compare/CompareResultPanel";
import "../styles/Home.css";

const EXAMPLE_PROMPT =
  "Please provide a detailed comparison focusing on:\n- Differences in coding decisions and interpretations\n- Patterns of agreement and disagreement\n- Quality and consistency of coding applications\n- Recommendations for improving coding reliability";

export default function CompareCoding() {
  const location = useLocation();
  const [items, setItems] = useState([]);
  const [a, setA] = useState(location.state?.codingA || "");
  const [b, setB] = useState("");
  const [loading, setLoading] = useState(false);
  const [comparison, setComparison] = useState("");
  const [error, setError] = useState("");
  const [model, setModel] = useState("");
  const [projects, setProjects] = useState([]);
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
            <CompareDualSelectPanel
              panelTitle="Select codings"
              labelA="Coding A"
              labelB="Coding B"
              placeholderOption="Select a coding"
              options={items}
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

        <CompareResultPanel
          comparison={comparison}
          fileType="coding_comparison"
          valueA={a}
          valueB={b}
          options={items}
          projects={projects}
        />
      </div>
    </div>
  );
}
