import { useEffect, useState } from "react";
import { requestJson } from "../../api";

/**
 * Find the Compare Codebook reports that were made from the codebooks
 * being integrated, so the researcher can read the comparison while
 * merging -- the intended compare-then-integrate workflow.
 *
 * No list endpoint of its own: a comparison is an `artifact_edges` child
 * of each codebook it compared, so `GET /api/artifacts/{ref}/lineage`
 * on every selected source already names them. Comparisons that cover
 * two (or more) of the selected codebooks sort first; ones touching
 * only one source still show, since they may still be useful reading.
 */
export function useSourceComparisons(refs) {
  const [comparisons, setComparisons] = useState([]);
  const [loading, setLoading] = useState(false);

  const key = (refs || []).join("|");

  useEffect(() => {
    if (!refs || refs.length === 0) {
      setComparisons([]);
      return undefined;
    }

    let cancelled = false;
    setLoading(true);

    (async () => {
      const results = await Promise.all(
        refs.map((ref) => requestJson(`/api/artifacts/${encodeURIComponent(ref)}/lineage`, { method: "GET" })),
      );
      if (cancelled) return;

      const byRef = new Map();
      results.forEach((result) => {
        if (!result.ok) return;
        for (const child of result.data?.children || []) {
          if (child.file_type !== "codebook_comparison" || !child.schema_name) continue;
          const entry = byRef.get(child.schema_name) || {
            ref: child.schema_name,
            name: child.filename || child.schema_name,
            coveredSources: 0,
          };
          entry.coveredSources += 1;
          byRef.set(child.schema_name, entry);
        }
      });

      const list = [...byRef.values()].sort((a, b) => b.coveredSources - a.coveredSources);
      setComparisons(list.map((entry) => ({ ...entry, coversSelection: entry.coveredSources >= 2 })));
      setLoading(false);
    })();

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
