import { useEffect, useState } from "react";
import { requestJson } from "../../api";

/**
 * Find the Compare Codebook reports made between at least two of the
 * codebooks being integrated (`GET /api/codebook-comparisons`), so the
 * researcher can read the comparison while merging.
 */
export function useSourceComparisons(refs) {
  const [comparisons, setComparisons] = useState([]);
  const [loading, setLoading] = useState(false);

  const key = (refs || []).join("|");

  useEffect(() => {
    if (!refs || refs.length < 2) {
      setComparisons([]);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);

    const query = refs.map((ref) => `codebooks=${encodeURIComponent(ref)}`).join("&");
    requestJson(`/api/codebook-comparisons?${query}`, { method: "GET" }).then((result) => {
      if (cancelled) return;
      const list = result.ok ? result.data?.comparisons || [] : [];
      setComparisons(list.map((cmp) => ({ ref: cmp.schema_name, name: cmp.filename || cmp.schema_name })));
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return { comparisons, loading };
}

/** Load one comparison report's markdown (`GET /api/codebook` serves a
 * `codebook_comparison` file's content as `codebook_comparison`). */
export function useComparisonContent(ref) {
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!ref) {
      setContent("");
      setError("");
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setError("");

    requestJson(`/api/codebook?codebook_id=${encodeURIComponent(ref)}`, { method: "GET" }).then((result) => {
      if (cancelled) return;
      if (!result.ok) {
        setError(result.error || "Failed to load the comparison");
        setContent("");
      } else {
        setContent(result.data?.codebook_comparison || "");
      }
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [ref]);

  return { content, loading, error };
}
