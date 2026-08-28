import { useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";

const SELECTION_CHANGE_DEBOUNCE_MS = 50;

// Identity throughout this module is `code_uid` (stable across a
// rename), never the display name `code` -- interval merging, the DOM
// round-trip, and color all key on it. `code` is carried alongside
// purely as the label shown in tooltips/popovers.

const buildNotesByCodeLookup = (codeEvidence) =>
  (codeEvidence || []).reduce((acc, entry) => {
    const codeUid = String(entry?.code_uid || "").trim();
    const notes = String(entry?.notes || "").trim();
    if (!codeUid || !notes) return acc;

    if (!acc[codeUid]) acc[codeUid] = new Set();
    acc[codeUid].add(notes);
    return acc;
  }, {});

/** `code_uid -> display name`, built once per render from whatever
 * evidence/available-codes props are on hand -- the DOM only ever
 * carries uids (see `data-code-uids` below), so this is how a stripe or
 * tooltip recovers a name to show.
 */
const buildNameByUidLookup = (codeEvidence, availableCodes) => {
  const map = {};
  (codeEvidence || []).forEach((entry) => {
    const uid = String(entry?.code_uid || "").trim();
    if (uid && entry?.code) map[uid] = entry.code;
  });
  (availableCodes || []).forEach((entry) => {
    const uid = String(entry?.code_uid || "").trim();
    if (uid && entry?.name) map[uid] = entry.name;
  });
  return map;
};

const addIntervalToSegment = (segment, interval) => {
  const codeUid = String(interval?.codeUid || "").trim();
  if (!codeUid) return;

  segment.codes.add(codeUid);

  const notes = String(interval?.notes || "").trim();
  if (!notes) return;

  if (!segment.notesByCode.has(codeUid)) {
    segment.notesByCode.set(codeUid, new Set());
  }
  segment.notesByCode.get(codeUid).add(notes);
};

/**
 * `codeEvidence` is one entry per quote (`{code, code_uid, quote,
 * start_offset, end_offset, notes}`, straight from `GET
 * /api/coding/{ref}/rows` -- see `coding_repo.list_rows_with_codes`),
 * already resolved to exact character offsets into `content`
 * server-side (either by `core/evidence_match.py` for an AI coding, or
 * by the real DOM selection range for a manual one -- see
 * `HighlightedContent`'s own selection handling below). There is nothing
 * left to search for at render time: an interval is just
 * `content.slice(start_offset, end_offset)`.
 */
const buildEvidenceIntervals = (content, codeEvidence) =>
  (codeEvidence || [])
    .filter(
      ({ code_uid: codeUid, start_offset, end_offset }) =>
        codeUid &&
        Number.isInteger(start_offset) &&
        Number.isInteger(end_offset) &&
        end_offset > start_offset &&
        start_offset >= 0 &&
        end_offset <= content.length,
    )
    .map(({ code_uid: codeUid, start_offset, end_offset, notes, quote }) => ({
      start: start_offset,
      end: end_offset,
      codeUid,
      quote,
      notes: String(notes || "").trim(),
    }));

const mergeIntervalsToSegments = (intervals) => {
  if (!intervals.length) return [];

  const sorted = [...intervals].sort((a, b) => a.start - b.start);
  const segments = [];

  sorted.forEach((interval) => {
    const overlapping = segments.find(
      (segment) => segment.start < interval.end && segment.end > interval.start,
    );

    if (overlapping) {
      overlapping.start = Math.min(overlapping.start, interval.start);
      overlapping.end = Math.max(overlapping.end, interval.end);
      addIntervalToSegment(overlapping, interval);
      return;
    }

    const segment = {
      start: interval.start,
      end: interval.end,
      codes: new Set(),
      notesByCode: new Map(),
    };
    addIntervalToSegment(segment, interval);
    segments.push(segment);
  });

  return segments;
};

/**
 * Character offset of `(node, offset)` within `root`'s rendered plain
 * text, counting every character of every text node from the start of
 * `root` up to that point. `root`'s text nodes render `content` verbatim
 * (just wrapped in `<span>`s for coded segments -- see `textAreaChildren`
 * below), so this offset lands in the same coordinate system as
 * `content` itself, and thus the same one `start_offset`/`end_offset`
 * from the server already use. This is what lets a manual "select text,
 * click a code" tag store an exact offset pair instead of re-searching
 * for the selected string later (the DOM selection *is* the ground
 * truth -- there is nothing to hallucinate here).
 */
function getTextOffsetInRoot(root, node, offset) {
  const preRange = document.createRange();
  preRange.selectNodeContents(root);
  preRange.setEnd(node, offset);
  return preRange.toString().length;
}

/** Pixel rect at the end of the selection (last character). */
function getSelectionEndClientRect(range) {
  const clone = range.cloneRange();
  clone.collapse(false);
  const rects = clone.getClientRects();
  if (rects.length > 0) {
    return rects[rects.length - 1];
  }
  return clone.getBoundingClientRect();
}

// Narrow gutter for code stripes (was 28px; keep step proportional so several codes still fit)
const CODING_MARGIN_WIDTH_PX = 18;
const MARGIN_STRIPE_STEP_PX = 4;
const MARGIN_STRIPE_WIDTH_PX = 2;
const MAX_CODING_MARGIN_WIDTH_PX = 32;

// Component for highlighted content with margin brackets
const HighlightedContent = ({
  content,
  codeEvidence,
  getCodeColor,
  availableCodes,
  onApplyCode,
  pendingSelection,
  onSelectionChange,
}) => {
  const containerRef = useRef(null);
  const textAreaRef = useRef(null);
  const marginRef = useRef(null);
  const selectionDebounceRef = useRef(null);
  // True for the whole span of a mouse-drag selection (mousedown ->
  // mouseup), regardless of where it started or how far the pointer
  // wanders. `selectionchange` fires continuously WHILE the button is
  // still held -- syncing mid-drag used to pop the code picker open on
  // a still-growing selection, and its `autoFocus` search input then
  // stole focus from the document, which aborts the native drag
  // right there (the selection gets cut off well before the user
  // finishes dragging). The debounced `selectionchange` path is
  // skipped entirely while this is true; only the eventual `mouseup`
  // finalizes a mouse-driven selection. Keyboard-driven selection
  // (Shift+Arrow, double-click-then-Shift-click) has no mousedown at
  // all, so it is untouched by this guard.
  const isMouseDownRef = useRef(false);
  // The live DOM range behind the current `pendingSelection` -- kept
  // only to reposition the popup on scroll (see the scroll listener
  // below). Never used to decide whether the selection is still "valid"
  // -- once captured, a pending selection is sticky (see module intent
  // below) and only ever cleared by an explicit action, not by the
  // browser collapsing/losing the underlying DOM selection.
  const lastRangeRef = useRef(null);
  const [lines, setLines] = useState([]);
  const [marginWidth, setMarginWidth] = useState(CODING_MARGIN_WIDTH_PX);
  const [tooltip, setTooltip] = useState(null); // { codeUids: [...], notesByCode: { [uid]: string[] }, x, y }
  const [popoverFilter, setPopoverFilter] = useState("");

  const nameByUid = buildNameByUidLookup(codeEvidence, availableCodes);

  const calculateLines = () => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    const codedSpans = container.querySelectorAll(".coded-span");

    const stripeCandidates = [];

    codedSpans.forEach((span) => {
      const codeUids = span.getAttribute("data-code-uids").split(",");
      const rect = span.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();

      const top = rect.top - containerRect.top;
      const height = rect.height;

      codeUids.forEach((codeUid, index) => {
        stripeCandidates.push({
          codeUid,
          top,
          height,
          color: getCodeColor(codeUid),
          order: index,
        });
      });
    });

    stripeCandidates.sort((a, b) => {
      if (a.top !== b.top) return a.top - b.top;
      if (a.height !== b.height) return b.height - a.height;
      return a.order - b.order;
    });

    const laneBottoms = [];
    const newLines = stripeCandidates.map((candidate) => {
      const lineBottom = candidate.top + candidate.height;
      let laneIndex = laneBottoms.findIndex(
        (laneBottom) => laneBottom <= candidate.top,
      );

      if (laneIndex === -1) {
        laneIndex = laneBottoms.length;
        laneBottoms.push(lineBottom);
      } else {
        laneBottoms[laneIndex] = lineBottom;
      }

      return {
        codeUid: candidate.codeUid,
        top: candidate.top,
        height: candidate.height,
        left: laneIndex * MARGIN_STRIPE_STEP_PX,
        color: candidate.color,
      };
    });

    const laneCount = laneBottoms.length;
    const requiredWidth =
      laneCount > 0
        ? (laneCount - 1) * MARGIN_STRIPE_STEP_PX + MARGIN_STRIPE_WIDTH_PX
        : CODING_MARGIN_WIDTH_PX;
    const boundedWidth = Math.min(
      MAX_CODING_MARGIN_WIDTH_PX,
      Math.max(CODING_MARGIN_WIDTH_PX, requiredWidth),
    );

    setLines(newLines);
    setMarginWidth(boundedWidth);
  };

  useEffect(() => {
    calculateLines();
  }, [content, codeEvidence, getCodeColor]);

  useEffect(() => {
    const handleResize = () => calculateLines();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [getCodeColor]);

  // Hide the hover tooltip (coded-span mouseover) on any scroll (window
  // or scrollable parent) -- unrelated to the selection popup below.
  useEffect(() => {
    if (!tooltip) return;
    const hide = () => setTooltip(null);
    window.addEventListener("scroll", hide, true);
    return () => window.removeEventListener("scroll", hide, true);
  }, [tooltip]);

  // -------------------------------------------------------------------
  // Selection -> code-picker popup.
  //
  // `pendingSelection` is owned by the parent (useViewCodingPage) --
  // this component only ever *reports* a newly captured selection up
  // via `onSelectionChange`, and renders the popup from the prop it's
  // given back. Once captured, a selection is STICKY: nothing in here
  // clears it just because the underlying browser selection collapsed
  // or moved (focusing the popup's own filter input collapses the
  // document selection, for instance -- that used to close the popup
  // the instant it opened). The captured `{text, start, end}` is
  // self-sufficient (the offsets already index straight into `content`),
  // so there is nothing left that depends on the live DOM selection
  // staying alive. Only an explicit action clears it: Escape, applying a
  // code, the reader's "Cancel", or the parent's own document-switch
  // effect.
  // -------------------------------------------------------------------

  const syncSelectionPopover = useCallback(() => {
    if (!onApplyCode || !textAreaRef.current) return;

    const sel = typeof window !== "undefined" ? window.getSelection() : null;
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return;

    const range = sel.getRangeAt(0);
    const root = textAreaRef.current;
    if (!root.contains(range.commonAncestorContainer)) return;

    const selectedText = sel.toString();
    if (!selectedText.trim()) return;

    // Compute the selection's offsets into `content` directly from the
    // real DOM range -- see getTextOffsetInRoot's comment for why this is
    // exact by construction rather than a search.
    const startOffset = getTextOffsetInRoot(root, range.startContainer, range.startOffset);
    const endOffset = startOffset + selectedText.length;

    lastRangeRef.current = range.cloneRange();
    setTooltip(null);
    const endRect = getSelectionEndClientRect(range);
    onSelectionChange?.({
      text: selectedText,
      start: startOffset,
      end: endOffset,
      left: endRect.left,
      top: endRect.bottom + 6,
    });
  }, [onApplyCode, onSelectionChange]);

  useEffect(() => {
    if (!onApplyCode) return undefined;

    const scheduleSync = () => {
      // While a mouse button is down, a selection is still being
      // dragged out -- let it finish; `onMouseUp` below does the real
      // sync the instant the drag ends. See isMouseDownRef's comment.
      if (isMouseDownRef.current) return;
      if (selectionDebounceRef.current != null) {
        clearTimeout(selectionDebounceRef.current);
      }
      selectionDebounceRef.current = window.setTimeout(() => {
        selectionDebounceRef.current = null;
        syncSelectionPopover();
      }, SELECTION_CHANGE_DEBOUNCE_MS);
    };

    const onMouseDown = () => {
      isMouseDownRef.current = true;
    };

    const onMouseUp = () => {
      isMouseDownRef.current = false;
      if (selectionDebounceRef.current != null) {
        clearTimeout(selectionDebounceRef.current);
        selectionDebounceRef.current = null;
      }
      syncSelectionPopover();
    };

    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("mouseup", onMouseUp);
    document.addEventListener("selectionchange", scheduleSync);

    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("mouseup", onMouseUp);
      document.removeEventListener("selectionchange", scheduleSync);
      if (selectionDebounceRef.current != null) {
        clearTimeout(selectionDebounceRef.current);
        selectionDebounceRef.current = null;
      }
    };
  }, [onApplyCode, syncSelectionPopover]);

  // A pending popup is REPOSITIONED (not closed) when the reader/sidebar
  // scrolls, from the last real range this component captured -- if that
  // range is no longer measurable (e.g. its text node was replaced by a
  // re-render), keep the last known position rather than guessing.
  useEffect(() => {
    if (!pendingSelection) return undefined;

    const reposition = () => {
      const range = lastRangeRef.current;
      if (!range) return;
      try {
        const endRect = getSelectionEndClientRect(range);
        onSelectionChange?.({ ...pendingSelection, left: endRect.left, top: endRect.bottom + 6 });
      } catch {
        // Range no longer resolvable -- leave the popup where it was.
      }
    };

    window.addEventListener("scroll", reposition, true);
    return () => window.removeEventListener("scroll", reposition, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingSelection?.text, pendingSelection?.start, pendingSelection?.end]);

  useEffect(() => {
    if (!pendingSelection) setPopoverFilter("");
  }, [pendingSelection]);

  // Escape dismisses an open popup. A fresh mousedown INSIDE the text
  // pane clears it too -- the user is starting a new selection (or just
  // clicking away within the text), and the following mouseup will
  // report a fresh one if a real selection results. A mousedown anywhere
  // else (the codebook sidebar, the popup itself) must NOT clear it --
  // that used to run in capture phase at the document level and fire
  // before the sidebar's own onClick could see a still-pending
  // selection, silently turning a tag-click into a filter-click.
  useEffect(() => {
    if (!pendingSelection) return undefined;
    const onKeyDown = (e) => {
      if (e.key === "Escape") onSelectionChange?.(null);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [pendingSelection, onSelectionChange]);

  const handleTextAreaMouseDown = () => {
    if (pendingSelection) onSelectionChange?.(null);
  };

  const showCodeTooltip = (e, codeUids, notesByCode = {}) => {
    setTooltip({ codeUids, notesByCode, x: e.clientX, y: e.clientY });
  };

  const moveTooltip = (e) => {
    setTooltip((prev) =>
      prev ? { ...prev, x: e.clientX, y: e.clientY } : null,
    );
  };

  const hideTooltip = () => setTooltip(null);

  const notesByCodeLookup = buildNotesByCodeLookup(codeEvidence);

  let textAreaChildren;
  if (!content) {
    textAreaChildren = null;
  } else if (!codeEvidence?.length) {
    textAreaChildren = <span>{content}</span>;
  } else {
    const intervals = buildEvidenceIntervals(content, codeEvidence);

    if (intervals.length === 0) {
      textAreaChildren = <span>{content}</span>;
    } else {
      const segments = mergeIntervalsToSegments(intervals);
      const elements = [];
      let lastEnd = 0;

      segments.forEach((segment, idx) => {
        if (segment.start > lastEnd) {
          elements.push(
            <span key={`text-${idx}`}>
              {content.slice(lastEnd, segment.start)}
            </span>,
          );
        }

        const segmentText = content.slice(segment.start, segment.end);
        const codeUids = Array.from(segment.codes);
        const notesByCode = codeUids.reduce((acc, codeUid) => {
          const notesFromSegment = segment.notesByCode.get(codeUid);
          if (notesFromSegment && notesFromSegment.size > 0) {
            acc[codeUid] = Array.from(notesFromSegment);
            return acc;
          }

          if (notesByCodeLookup[codeUid] && notesByCodeLookup[codeUid].size > 0) {
            acc[codeUid] = Array.from(notesByCodeLookup[codeUid]);
          }

          return acc;
        }, {});

        elements.push(
          <span
            key={`segment-${idx}`}
            className="coded-span relative cursor-pointer bg-paper px-0.5 py-px text-ink"
            data-code-uids={codeUids.join(",")}
            onMouseEnter={(e) => showCodeTooltip(e, codeUids, notesByCode)}
            onMouseMove={moveTooltip}
            onMouseLeave={hideTooltip}
          >
            {segmentText}
          </span>,
        );

        lastEnd = segment.end;
      });

      if (lastEnd < content.length) {
        elements.push(<span key="remaining">{content.slice(lastEnd)}</span>);
      }

      textAreaChildren = elements;
    }
  }

  const handleApplyCodeClick = (codeUid) => (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!pendingSelection?.text || !onApplyCode) return;
    // The parent (useViewCodingPage's applyCodeToSelection) reads the
    // pending selection from its own state -- this call just triggers it.
    onApplyCode(codeUid);
    onSelectionChange?.(null);
  };

  const filteredPopoverCodes = (availableCodes || []).filter((code) =>
    (code.name || "").toLowerCase().includes(popoverFilter.trim().toLowerCase()),
  );

  return (
    <>
      <div
        className="relative flex bg-ink text-paper"
        ref={containerRef}
      >
        <div
          className="flex-1 leading-relaxed"
          ref={textAreaRef}
          onMouseDown={handleTextAreaMouseDown}
          style={{ padding: "8px 6px 8px 8px" }}
        >
          {textAreaChildren}
        </div>
        <div
          className="relative ml-1 shrink-0 self-stretch overflow-hidden bg-white/5"
          ref={marginRef}
          style={{ width: `${marginWidth}px` }}
        >
          {lines.map((line, idx) => (
            <div
              key={idx}
              className="absolute cursor-pointer transition-opacity hover:opacity-80"
              style={{
                width: `${MARGIN_STRIPE_WIDTH_PX}px`,
                height: `${line.height}px`,
                top: `${line.top}px`,
                left: `${line.left}px`,
                backgroundColor: line.color,
              }}
              onMouseEnter={(e) =>
                showCodeTooltip(
                  e,
                  [line.codeUid],
                  notesByCodeLookup[line.codeUid] &&
                    notesByCodeLookup[line.codeUid].size > 0
                    ? { [line.codeUid]: Array.from(notesByCodeLookup[line.codeUid]) }
                    : {},
                )
              }
              onMouseMove={moveTooltip}
              onMouseLeave={hideTooltip}
            />
          ))}
        </div>
      </div>
      {tooltip && (
        <div
          className="fixed z-[10000] max-w-[300px] break-words border border-paper bg-ink px-4 py-3 text-sm font-medium text-paper shadow-lg"
          style={{
            left: tooltip.x + 12,
            top: tooltip.y + 12,
          }}
        >
          <div className="mb-1.5 text-xs font-bold uppercase tracking-wide text-paper/60">
            Codes:
          </div>
          {tooltip.codeUids.map((codeUid) => (
            <div key={codeUid} className="mb-2 flex flex-col items-start gap-1">
              <div className="flex items-center">
                <div
                  className="mr-2 h-2.5 w-2.5 shrink-0"
                  style={{ backgroundColor: getCodeColor(codeUid) }}
                />
                <span className="font-semibold">{nameByUid[codeUid] || codeUid}</span>
              </div>
              {Array.isArray(tooltip.notesByCode?.[codeUid]) &&
                tooltip.notesByCode[codeUid].length > 0 && (
                  <div className="ml-[18px] max-w-[260px] text-xs leading-snug text-paper/70">
                    <div className="mb-0.5 text-[11px] font-bold uppercase tracking-wide text-paper/50">
                      Notes
                    </div>
                    {tooltip.notesByCode[codeUid].map((note, index) => (
                      <div key={`${codeUid}-tooltip-note-${index}`}>{note}</div>
                    ))}
                  </div>
                )}
            </div>
          ))}
        </div>
      )}
      {pendingSelection &&
        onApplyCode &&
        createPortal(
          <div
            className="fixed z-[10001] flex max-h-[260px] w-[220px] flex-col border border-paper bg-ink p-2 shadow-lg"
            style={{
              left: pendingSelection.left,
              top: pendingSelection.top,
            }}
            role="dialog"
            aria-label="Tag selected text with a code"
          >
            <input
              autoFocus
              type="text"
              value={popoverFilter}
              onChange={(e) => setPopoverFilter(e.target.value)}
              placeholder="Search codes..."
              className="mb-1.5 border border-paper bg-white/5 px-2 py-1 text-xs text-paper placeholder:text-paper/40 focus:outline-none focus:ring-1 focus:ring-paper"
            />
            <div className="flex flex-col gap-1 overflow-y-auto">
              {filteredPopoverCodes.length === 0 ? (
                <div className="px-1 py-1 text-xs text-paper/50">No matching codes</div>
              ) : (
                filteredPopoverCodes.map((code) => (
                  <button
                    key={code.code_uid}
                    type="button"
                    className="flex items-center gap-1.5 truncate border border-transparent px-1.5 py-1 text-left text-xs transition-colors hover:border-paper hover:bg-white/10"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={handleApplyCodeClick(code.code_uid)}
                    title={code.name}
                  >
                    <span
                      className="h-2.5 w-2.5 shrink-0"
                      style={{ backgroundColor: getCodeColor(code.code_uid) }}
                    />
                    <span className="truncate">{code.name}</span>
                  </button>
                ))
              )}
            </div>
          </div>,
          document.body,
        )}
    </>
  );
};

export default HighlightedContent;
