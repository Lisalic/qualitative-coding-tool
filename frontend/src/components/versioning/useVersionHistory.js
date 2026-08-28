import { useCallback, useState } from "react";
import { requestJson } from "../../api";

/**
 * Version history for any artifact -- the backend routes
 * (`/api/artifacts/{ref}/versions`/`diff`, see
 * `backend/app/api/version_routes.py`) are generic across every file
 * type, so this one hook backs both the codebook page and the coding
 * workspace's history panel. `diff` is `{codebook: {...}, coding: {...}
 * | null}` -- `coding` is only non-null for a `coding` file (see the
 * route's docstring).
 *
 * There is no revert here -- recovering an old state is "duplicate from
 * that version" instead, which is per-artifact-type (different endpoint
 * for codebook vs. coding) and so lives outside this generic hook; see
 * `VersionHistoryPanel`'s `onDuplicateFrom` prop. There is also no
 * checkpoint any more -- every commit is sealed the instant it's
 * created (see `version_service.py`'s module docstring), so a
 * user-triggered "seal this" action never had anything left to do.
 */
export default function useVersionHistory(ref) {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [diff, setDiff] = useState(null);
  const [diffLoading, setDiffLoading] = useState(false);

  const fetchVersions = useCallback(async () => {
    if (!ref) {
      setVersions([]);
      return;
    }
    setLoading(true);
    setError(null);
    const result = await requestJson(`/api/artifacts/${encodeURIComponent(ref)}/versions`, { method: "GET" });
    setLoading(false);
    if (!result.ok) {
      setError(result.error || "Failed to load version history.");
      return;
    }
    setVersions(result.data.versions || []);
  }, [ref]);

  const fetchDiff = useCallback(
    async (fromNo, toNo) => {
      if (!ref) return;
      setDiffLoading(true);
      setDiff(null);
      const result = await requestJson(
        `/api/artifacts/${encodeURIComponent(ref)}/diff?from_no=${fromNo}&to_no=${toNo}`,
        { method: "GET" },
      );
      setDiffLoading(false);
      if (!result.ok) {
        setError(result.error || "Failed to compute diff.");
        return;
      }
      setDiff(result.data);
    },
    [ref],
  );

  const clearDiff = useCallback(() => setDiff(null), []);

  return {
    versions,
    loading,
    error,
    diff,
    diffLoading,
    fetchVersions,
    fetchDiff,
    clearDiff,
  };
}
