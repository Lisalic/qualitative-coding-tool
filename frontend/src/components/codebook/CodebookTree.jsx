import React, { useEffect, useState, useCallback } from "react";
import { apiFetch } from "../../api";
import ReactMarkdown from "react-markdown";

const actionBtn =
  "ml-2 border border-paper px-2.5 py-1.5 text-xs transition-colors hover:bg-paper hover:text-ink";

export default function CodebookTree({
  codebookId = null,
  codebookName = null,
}) {
  const [tree, setTree] = useState([]);
  const [expanded, setExpanded] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchParsed = useCallback(async () => {
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
      (j.parsed || []).forEach((_, i) => {
        init[i] = true;
      });
      setExpanded(init);
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }, [codebookId]);

  useEffect(() => {
    fetchParsed();
  }, [fetchParsed]);

  const toggleFamily = (idx) => {
    setExpanded((s) => ({ ...s, [idx]: !s[idx] }));
  };

  return (
    <div className="border border-paper p-4">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-lg font-semibold">{codebookName || "Codebook"}</h3>
        <div>
          <button
            type="button"
            className={actionBtn}
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
          <button type="button" className={actionBtn} onClick={() => setExpanded({})}>
            Collapse All
          </button>
        </div>
      </div>

      {loading && <div className="p-2 text-paper/70">Loading...</div>}
      {error && <div className="p-2 text-error">{error}</div>}

      {!loading && !error && (
        <div>
          {tree.length === 0 && (
            <div className="p-2 text-paper/70">No codebook content found.</div>
          )}
          {tree.map((family, fi) => (
            <div className="my-2" key={fi}>
              <div
                className="flex cursor-pointer items-center gap-2 border border-paper/20 px-3 py-2 transition-colors hover:bg-white/5"
                onClick={() => toggleFamily(fi)}
              >
                <span className="inline-block w-4 text-center">
                  {expanded[fi] ? "▾" : "▸"}
                </span>
                <strong>{family.family_name || `Family ${fi + 1}`}</strong>
              </div>
              {expanded[fi] && (
                <ul className="mt-1.5 list-none pl-5">
                  {(family.codes || []).map((code, ci) => (
                    <li
                      className="mb-1.5 border-l-2 border-paper/30 py-2 pl-3"
                      key={ci}
                    >
                      <div className="font-semibold">
                        {code.code_name || `Code ${ci + 1}`}
                      </div>
                      <div className="mt-1 text-sm text-paper/80">
                        {code.content ? (
                          <ReactMarkdown>{code.content}</ReactMarkdown>
                        ) : (
                          "(no content)"
                        )}
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
