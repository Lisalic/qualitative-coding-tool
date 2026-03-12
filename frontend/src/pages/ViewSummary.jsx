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
    <div className="layout-page">
      <div className="layout-card layout-card--padded" style={{ width: "100%", maxWidth: 900 }}>
        <div className="panel panel-body">
          <div className="layout-flex-col gap-sm" style={{ marginBottom: 16 }}>
            <div style={{ width: "100%" }}>
              <SelectionList
                className="selector-strip"
                buttonClass="selector-button"
                items={available}
                selectedId={selected}
                onSelect={(id) => setSelected(id)}
                emptyMessage="No summaries available"
              />
            </div>

            <div className="layout-space-between">
              <h2 className="heading-md">
                {selectedName || "Select a summary"}
              </h2>
            </div>

            {loading && <div className="alert alert--info">Loading...</div>}
            {error && <div className="alert alert--error">{error}</div>}

            <div className="body-base text-primary">
              <ReactMarkdown>{content}</ReactMarkdown>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
