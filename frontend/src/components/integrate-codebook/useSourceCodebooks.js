import { useEffect, useState } from "react";
import { requestJson } from "../../api";
import { groupCodesByFamily } from "../../lib/codingUtils";

/**
 * Load the full content of every source codebook selected for
 * integration, in the caller's own order.
 *
 * `GET /api/codebook?codebook_id=<ref>` already returns everything the
 * left pane and the AI panel need (`{codes, systemprompt, instructions,
 * prompt_meta, version_no}`) -- no new endpoint. One request per ref, in
 * parallel: the selection is small (a handful of codebooks at most), and
 * a merge review is inherently "read every source before doing anything
 * else" rather than a paginated browse.
 */
export function useSourceCodebooks(refs) {
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const key = (refs || []).join("|");

  useEffect(() => {
    if (!refs || refs.length === 0) {
      setSources([]);
      setError("");
      return undefined;
    }

    let cancelled = false;
    setLoading(true);
    setError("");

    (async () => {
      const results = await Promise.all(
        refs.map((ref) => requestJson(`/api/codebook?codebook_id=${encodeURIComponent(ref)}`, { method: "GET" })),
      );
      if (cancelled) return;

      const failed = results.find((r) => !r.ok);
      if (failed) {
        setError(failed.error || "Failed to load one of the selected codebooks");
        setSources([]);
        setLoading(false);
        return;
      }

      setSources(
        refs.map((ref, i) => ({
          ref,
          codes: results[i].data?.codes || [],
          tree: groupCodesByFamily(results[i].data?.codes || []),
        })),
      );
      setLoading(false);
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return { sources, loading, error };
}
