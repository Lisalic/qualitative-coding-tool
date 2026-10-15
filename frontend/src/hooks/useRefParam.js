import { useCallback, useEffect } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * Mirrors a view page's selected file into the URL as `?ref=<schema>`,
 * the same parameter Lineage and Version History already use -- so a
 * refresh, a Back from another page, or a copied link reopens the same
 * file instead of the empty picker.
 *
 * Returns the `ref` currently in the URL (a page treats it as one more
 * preselection source, alongside any `location.state` a link passed).
 * Whenever `selected` changes it is written back with `replace`, so
 * picking files doesn't stack up history entries.
 */
export function useRefParam(selected, { enabled = true } = {}) {
  const [searchParams, setSearchParams] = useSearchParams();
  const urlRef = searchParams.get("ref") || null;

  const writeRef = useCallback(
    (ref) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (ref) next.set("ref", String(ref));
          else next.delete("ref");
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  useEffect(() => {
    if (!enabled || !selected) return;
    if (String(selected) === urlRef) return;
    writeRef(selected);
    // Only a new selection should write; `urlRef` changing on its own
    // (Back/Forward) is read by the page as a preselection instead.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, selected]);

  return urlRef;
}
