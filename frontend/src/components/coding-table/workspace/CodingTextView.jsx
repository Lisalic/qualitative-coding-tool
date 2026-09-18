import { useEffect, useState } from "react";
import { apiFetch } from "../../../api";
import PageEmptyState from "../../primitives/PageEmptyState";

/**
 * Read-only rendering of a coding artifact's classification, generated
 * fresh server-side from `coding_entries` (the sole source of truth --
 * see `coding_repo.render_coding_text`). There is no editable text view
 * any more: every edit goes through the structured table, which is what
 * actually gets saved.
 */
export default function CodingTextView({ schema, refreshKey }) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!schema) {
      setText("");
      return;
    }
    let mounted = true;
    setLoading(true);
    setError(null);
    apiFetch(`/api/coding/${encodeURIComponent(schema)}/text`)
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        if (!mounted) return;
        setText(data?.text || "");
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err?.message || "Failed to load coding text");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [schema, refreshKey]);

  if (loading) {
    return (
      <div className="border border-paper/20 bg-white/5 px-4 py-3 text-sm text-paper/70">
        Loading...
      </div>
    );
  }

  if (error) {
    return (
      <div className="border border-error bg-error/10 px-3 py-2 text-sm text-error">{error}</div>
    );
  }

  if (!text) {
    return <PageEmptyState message="Nothing has been coded yet." />;
  }

  return (
    <pre className="h-full min-h-0 overflow-auto whitespace-pre-wrap break-words border border-line bg-surface-raised p-3 font-mono text-sm text-paper">
      {text}
    </pre>
  );
}
