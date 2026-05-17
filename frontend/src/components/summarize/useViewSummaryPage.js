import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch } from "../../api";

export default function useViewSummaryPage() {
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
    apiFetch("/api/my-files/?file_type=summary")
      .then((response) => (mounted && response.ok ? response.json() : Promise.reject(response)))
      .then((data) => {
        if (!mounted) return;
        const items = (data.projects || []).map((project) => ({
          id: project.schema_name || project.id,
          name: project.schema_name || String(project.id),
          display_name:
            project.display_name || project.schema_name || String(project.id),
          description: project.description || "",
        }));
        setAvailable(items);
        if (!preselect) return;
        setSelected(preselect);
        const match = items.find((item) => item.id === preselect);
        if (match) setSelectedName(match.display_name || match.name);
      })
      .catch(() => {});
    return () => {
      mounted = false;
    };
  }, [preselect]);

  useEffect(() => {
    let mounted = true;
    if (!selected) {
      setContent("");
      return () => {
        mounted = false;
      };
    }
    setLoading(true);
    setError(null);
    apiFetch(`/api/summary/${encodeURIComponent(selected)}`)
      .then((response) => {
        if (!mounted) return null;
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        if (!mounted || !data) return;
        const summary = data.summary || data || {};
        setContent(summary.content || summary.summary || JSON.stringify(summary, null, 2));
        setSelectedName(summary.display_name || summary.name || selected);
      })
      .catch((fetchError) => {
        if (!mounted) return;
        setError(fetchError.message || "Failed to load summary");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [selected]);

  return {
    available,
    selected,
    setSelected,
    selectedName,
    content,
    loading,
    error,
  };
}
