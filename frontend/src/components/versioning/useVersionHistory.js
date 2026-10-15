import { useCallback, useRef, useState } from "react";
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
 *
 * Only the newest request of each kind may write state: switching the
 * ref while a slow `/versions` or `/diff` is in flight used to let the
 * previous artifact's answer land last and show under the new one, and
 * a diff started for v1/v2 could fill in after the user had moved on to
 * v3 ("Diff v3 -> v3" over v1/v2 data).
 */
export default function useVersionHistory(ref) {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [diff, setDiff] = useState(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const versionsRequest = useRef(0);
  const diffRequest = useRef(0);

  const fetchVersions = useCallback(async () => {
    const requestId = ++versionsRequest.current;
    if (!ref) {
      setVersions([]);
      return;
    }
    setLoading(true);
    setError(null);
    const result = await requestJson(`/api/artifacts/${encodeURIComponent(ref)}/versions`, { method: "GET" });
    if (requestId !== versionsRequest.current) return;
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
      const requestId = ++diffRequest.current;
      setDiffLoading(true);
      setDiff(null);
      const result = await requestJson(
        `/api/artifacts/${encodeURIComponent(ref)}/diff?from_no=${fromNo}&to_no=${toNo}`,
        { method: "GET" },
      );
      if (requestId !== diffRequest.current) return;
      setDiffLoading(false);
      if (!result.ok) {
        setError(result.error || "Failed to compute diff.");
        return;
      }
      setDiff(result.data);
    },
    [ref],
  );

  // Clearing also discards any diff still in flight, so it can't reappear
  // under a different selection.
  const clearDiff = useCallback(() => {
    diffRequest.current += 1;
    setDiffLoading(false);
    setDiff(null);
  }, []);

  return {
    ref,
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
