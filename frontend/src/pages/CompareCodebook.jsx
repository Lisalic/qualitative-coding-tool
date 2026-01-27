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
                  <option value="">Default</option>
                  <option value="MODEL_1">MODEL_1</option>
                  <option value="MODEL_2">MODEL_2</option>
                  <option value="MODEL_3">MODEL_3</option>
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
            </div>
            <div className="comparison-output" style={{ marginTop: 8 }}>
              {comparison}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
