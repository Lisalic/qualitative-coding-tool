import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch } from "../api";
import SelectionList from "../components/SelectionList";
import ReactMarkdown from "react-markdown";
import "../styles/Home.css";

export default function ViewSummary() {
  const location = useLocation();
  const preselect = location?.state?.selectedSummary || null;

  const [available, setAvailable] = useState([]);
  const [selected, setSelected] = useState(preselect);
  const [selectedName, setSelectedName] = useState("");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    // fetch available summaries for selection
    apiFetch("/api/my-files/?file_type=summary")
      .then((r) => (mounted && r.ok ? r.json() : Promise.reject(r)))
      .then((data) => {
        if (!mounted) return;
        const items = (data.projects || []).map((p) => ({
          id: p.schema_name || p.id,
          name: p.schema_name || String(p.id),
          display_name: p.display_name || p.schema_name || String(p.id),
          description: p.description || "",
        }));
        setAvailable(items);
        if (preselect) {
          setSelected(preselect);
          const match = items.find((it) => it.id === preselect);
          if (match) setSelectedName(match.display_name || match.name);
        }
      })
      .catch(() => {})
      .finally(() => (mounted = false));
    return () => (mounted = false);
  }, [preselect]);

  useEffect(() => {
    let mounted = true;
    if (!selected) {
      setContent("");
      return () => (mounted = false);
    }
    setLoading(true);
    setError(null);
    apiFetch(`/api/summary/${encodeURIComponent(selected)}`)
      .then((r) => {
        if (!mounted) return;
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (!mounted) return;
        // assume endpoint returns { summary: { content, display_name, description } } or raw
        const s = data.summary || data || {};
        setContent(s.content || s.summary || JSON.stringify(s, null, 2));
        setSelectedName(s.display_name || s.name || selectedName || selected);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err.message || "Failed to load summary");
      })
      .finally(() => mounted && setLoading(false));

    return () => (mounted = false);
  }, [selected]);

  return (
    <div className="home-container">
      <div className="form-wrapper">
        <div
          style={{
            backgroundColor: "#000000",
            border: "2px solid #ffffff",
            borderRadius: 12,
            padding: 24,
          }}
        >
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 12,
              marginBottom: 16,
            }}
          >
            <div style={{ width: "100%" }}>
              <SelectionList
                className="database-selector"
                buttonClass="db-button"
                items={available}
                selectedId={selected}
                onSelect={(id) => setSelected(id)}
                emptyMessage="No summaries available"
              />
            </div>

            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <h2 style={{ color: "#ffffff", margin: 0 }}>
                {selectedName || "Select a summary"}
              </h2>
            </div>

            {loading && <div style={{ color: "#ffffff" }}>Loading...</div>}
            {error && <div style={{ color: "#ff6b6b" }}>{error}</div>}

            <div style={{ marginTop: 0, color: "#ffffff" }}>
              <ReactMarkdown>{content}</ReactMarkdown>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
