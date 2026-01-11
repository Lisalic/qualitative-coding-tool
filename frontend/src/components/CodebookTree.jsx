import React, { useEffect, useState } from "react";
import { apiFetch } from "../api";
import "../styles/CodebookTree.css";

export default function CodebookTree({
  codebookId = null,
  codebookName = null,
}) {
  const [tree, setTree] = useState([]);
  const [expanded, setExpanded] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchParsed();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [codebookId]);

  async function fetchParsed() {
    setLoading(true);
    setError(null);
    try {
      const q = codebookId
        ? `?codebook_id=${encodeURIComponent(codebookId)}`
        : "";
      const resp = await apiFetch(`/api/parse-codebook${q}`);
      if (!resp.ok) throw new Error("Failed to fetch parsed codebook");
      const j = await resp.json();
      if (j.error) throw new Error(j.error);
      setTree(j.parsed || []);
      // expand all families by default
      const init = {};
      (j.parsed || []).forEach((f, i) => (init[i] = true));
      setExpanded(init);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  function toggleFamily(idx) {
    setExpanded((s) => ({ ...s, [idx]: !s[idx] }));
  }

  return (
    <div className="codebook-tree">
      <div className="codebook-tree-header">
        <h3>{codebookName || "Codebook"}</h3>
        <div className="codebook-tree-actions">
          <button
            onClick={() =>
              setExpanded((s) => {
                const all = {};
                tree.forEach((_, i) => (all[i] = true));
                return all;
              })
            }
          >
            Expand All
          </button>
          <button onClick={() => setExpanded({})}>Collapse All</button>
        </div>
      </div>

      {loading && <div className="cb-loading">Loading...</div>}
      {error && <div className="cb-error">{error}</div>}

      {!loading && !error && (
        <div className="cb-list">
          {tree.length === 0 && (
            <div className="cb-empty">No codebook content found.</div>
          )}
          {tree.map((family, fi) => (
            <div className="cb-family" key={fi}>
              <div className="cb-family-title" onClick={() => toggleFamily(fi)}>
                <span className="cb-toggle">{expanded[fi] ? "▾" : "▸"}</span>
                <strong>{family.family_name || `Family ${fi + 1}`}</strong>
              </div>
              {expanded[fi] && (
                <ul className="cb-codes">
                  {(family.codes || []).map((code, ci) => (
                    <li className="cb-code" key={ci}>
                      <div className="cb-code-name">
                        {code.code_name || `Code ${ci + 1}`}
                      </div>
                      <div className="cb-code-def">
                        {code.definition || "(no definition)"}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
