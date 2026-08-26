import { useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";

const SELECTION_CHANGE_DEBOUNCE_MS = 50;

const buildNotesByCodeLookup = (codeEvidence) =>
  (codeEvidence || []).reduce((acc, entry) => {
    const code = String(entry?.code || "").trim();
    const notes = String(entry?.notes || "").trim();
    if (!code || !notes) return acc;

    if (!acc[code]) acc[code] = new Set();
    acc[code].add(notes);
    return acc;
  }, {});

const addIntervalToSegment = (segment, interval) => {
  const code = String(interval?.code || "").trim();
  if (!code) return;

  segment.codes.add(code);

  const notes = String(interval?.notes || "").trim();
  if (!notes) return;

  if (!segment.notesByCode.has(code)) {
    segment.notesByCode.set(code, new Set());
  }
  segment.notesByCode.get(code).add(notes);
};

/**
 * `codeEvidence` is one entry per quote (`{code, quote, start_offset,
 * end_offset, notes}`, straight from `GET /api/coding/{ref}/rows` -- see
 * `coding_repo.list_rows_with_codes`), already resolved to exact
 * character offsets into `content` server-side (either by
 * `core/evidence_match.py` for an AI coding, or by the real DOM selection
 * range for a manual one -- see `HighlightedContent`'s own selection
 * handling below). There is nothing left to search for at render time:
 * an interval is just `content.slice(start_offset, end_offset)`.
 */
const buildEvidenceIntervals = (content, codeEvidence) =>
  (codeEvidence || [])
    .filter(
      ({ code, start_offset, end_offset }) =>
        code &&
        Number.isInteger(start_offset) &&
        Number.isInteger(end_offset) &&
        end_offset > start_offset &&
        start_offset >= 0 &&
        end_offset <= content.length,
    )
    .map(({ code, start_offset, end_offset, notes, quote }) => ({
      start: start_offset,
      end: end_offset,
      code,
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
  onSelectionChange,
}) => {
  const containerRef = useRef(null);
  const textAreaRef = useRef(null);
  const marginRef = useRef(null);
  const selectionPopoverRef = useRef(null);
  const selectionDebounceRef = useRef(null);
  const [lines, setLines] = useState([]);
  const [marginWidth, setMarginWidth] = useState(CODING_MARGIN_WIDTH_PX);
  const [tooltip, setTooltip] = useState(null); // { codes: [...], notesByCode: { [code]: string[] }, x, y }
  const [selectionPopover, setSelectionPopover] = useState(null); // { left, top, selectedText }
  const [popoverFilter, setPopoverFilter] = useState("");

  const calculateLines = () => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    const codedSpans = container.querySelectorAll(".coded-span");

    const stripeCandidates = [];

    codedSpans.forEach((span) => {
      const codes = span.getAttribute("data-codes").split(",");
      const rect = span.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();

      const top = rect.top - containerRect.top;
      const height = rect.height;

      codes.forEach((code, index) => {
        stripeCandidates.push({
          code,
          top,
          height,
          color: getCodeColor(code),
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
        code: candidate.code,
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

  // Hide tooltip on any scroll (window or scrollable parent)
  useEffect(() => {
    if (!tooltip) return;
    const hide = () => setTooltip(null);
    window.addEventListener("scroll", hide, true);
    return () => window.removeEventListener("scroll", hide, true);
  }, [tooltip]);

  const syncSelectionPopover = useCallback(() => {
    if (!onApplyCode || !textAreaRef.current) {
      setSelectionPopover(null);
      return;
    }

    const sel = typeof window !== "undefined" ? window.getSelection() : null;
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) {
      setSelectionPopover(null);
      return;
    }

    const range = sel.getRangeAt(0);
    const root = textAreaRef.current;
    if (!root.contains(range.commonAncestorContainer)) {
      setSelectionPopover(null);
      return;
    }

    const selectedText = sel.toString();
    if (!selectedText.trim()) {
      setSelectionPopover(null);
      return;
    }

    // Compute the selection's offsets into `content` directly from the
    // real DOM range -- see getTextOffsetInRoot's comment for why this is
    // exact by construction rather than a search.
    const startOffset = getTextOffsetInRoot(root, range.startContainer, range.startOffset);
    const endOffset = startOffset + selectedText.length;

    setTooltip(null);
    const endRect = getSelectionEndClientRect(range);
    setSelectionPopover({
      left: endRect.left,
      top: endRect.bottom + 6,
      selectedText,
      startOffset,
      endOffset,
    });
  }, [onApplyCode]);

  useEffect(() => {
    if (!onApplyCode) {
      setSelectionPopover(null);
      return undefined;
    }

    const scheduleSync = () => {
      if (selectionDebounceRef.current != null) {
        clearTimeout(selectionDebounceRef.current);
      }
      selectionDebounceRef.current = window.setTimeout(() => {
        selectionDebounceRef.current = null;
        syncSelectionPopover();
      }, SELECTION_CHANGE_DEBOUNCE_MS);
    };

    const onMouseUp = () => {
      if (selectionDebounceRef.current != null) {
        clearTimeout(selectionDebounceRef.current);
        selectionDebounceRef.current = null;
      }
      syncSelectionPopover();
    };

    document.addEventListener("mouseup", onMouseUp);
    document.addEventListener("selectionchange", scheduleSync);

    return () => {
      document.removeEventListener("mouseup", onMouseUp);
      document.removeEventListener("selectionchange", scheduleSync);
      if (selectionDebounceRef.current != null) {
        clearTimeout(selectionDebounceRef.current);
        selectionDebounceRef.current = null;
      }
    };
  }, [onApplyCode, syncSelectionPopover]);

  // Report the pending selection (or null when cleared) up to the parent,
  // so e.g. the codebook sidebar can show a "tagging" banner and apply a
  // code by click from there too, not just from this popover. Depends on
  // the primitive text/start/end, not the `selectionPopover` object
  // reference, and expects `onSelectionChange` to be a stable callback --
  // otherwise a new reference on every parent re-render would re-fire
  // this effect every render regardless of whether the selection changed,
  // which (if the parent's handler updates state unconditionally) is a
  // feedback loop: re-render -> new callback -> effect fires -> state
  // update -> re-render -> ...
  const selectedText = selectionPopover?.selectedText || null;
  const selectedStart = selectionPopover?.startOffset ?? null;
  const selectedEnd = selectionPopover?.endOffset ?? null;
  useEffect(() => {
    if (!onSelectionChange) return;
    onSelectionChange(
      selectedText ? { text: selectedText, start: selectedStart, end: selectedEnd } : null,
    );
  }, [onSelectionChange, selectedText, selectedStart, selectedEnd]);

  useEffect(() => {
    if (!selectionPopover) setPopoverFilter("");
  }, [selectionPopover]);

  useEffect(() => {
    if (!selectionPopover) return;

    const onKeyDown = (e) => {
      if (e.key === "Escape") setSelectionPopover(null);
    };

    const onScroll = () => setSelectionPopover(null);

    const onMouseDownCapture = (e) => {
      if (selectionPopoverRef.current?.contains(e.target)) return;
      setSelectionPopover(null);
    };

    document.addEventListener("keydown", onKeyDown);
    window.addEventListener("scroll", onScroll, true);
    document.addEventListener("mousedown", onMouseDownCapture, true);

    return () => {
      document.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("scroll", onScroll, true);
      document.removeEventListener("mousedown", onMouseDownCapture, true);
    };
  }, [selectionPopover]);

  const showCodeTooltip = (e, codes, notesByCode = {}) => {
    setTooltip({ codes, notesByCode, x: e.clientX, y: e.clientY });
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
        const codes = Array.from(segment.codes);
        const notesByCode = codes.reduce((acc, code) => {
          const notesFromSegment = segment.notesByCode.get(code);
          if (notesFromSegment && notesFromSegment.size > 0) {
            acc[code] = Array.from(notesFromSegment);
            return acc;
          }

          if (notesByCodeLookup[code] && notesByCodeLookup[code].size > 0) {
            acc[code] = Array.from(notesByCodeLookup[code]);
          }

          return acc;
        }, {});

        elements.push(
          <span
            key={`segment-${idx}`}
            className="relative cursor-pointer bg-paper px-0.5 py-px text-ink"
            data-codes={codes.join(",")}
            onMouseEnter={(e) => showCodeTooltip(e, codes, notesByCode)}
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

  const handleApplyCodeClick = (code) => (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!selectionPopover?.selectedText || !onApplyCode) return;
    // The parent (useViewCodingPage's applyCodeToSelection) reads the
    // pending selection from its own state, kept in sync by the
    // onSelectionChange effect above -- this call just triggers it.
    onApplyCode(code, {
      text: selectionPopover.selectedText,
      start: selectionPopover.startOffset,
      end: selectionPopover.endOffset,
    });
    setSelectionPopover(null);
    window.getSelection()?.removeAllRanges();
  };

  const filteredPopoverCodes = (availableCodes || []).filter((code) =>
    code.toLowerCase().includes(popoverFilter.trim().toLowerCase()),
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
                  [line.code],
                  notesByCodeLookup[line.code] &&
                    notesByCodeLookup[line.code].size > 0
                    ? { [line.code]: Array.from(notesByCodeLookup[line.code]) }
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
          {tooltip.codes.map((code) => (
            <div key={code} className="mb-2 flex flex-col items-start gap-1">
              <div className="flex items-center">
                <div
                  className="mr-2 h-2.5 w-2.5 shrink-0"
                  style={{ backgroundColor: getCodeColor(code) }}
                />
                <span className="font-semibold">{code}</span>
              </div>
              {Array.isArray(tooltip.notesByCode?.[code]) &&
                tooltip.notesByCode[code].length > 0 && (
                  <div className="ml-[18px] max-w-[260px] text-xs leading-snug text-paper/70">
                    <div className="mb-0.5 text-[11px] font-bold uppercase tracking-wide text-paper/50">
                      Notes
                    </div>
                    {tooltip.notesByCode[code].map((note, index) => (
                      <div key={`${code}-tooltip-note-${index}`}>{note}</div>
                    ))}
                  </div>
                )}
            </div>
          ))}
        </div>
      )}
      {selectionPopover &&
        onApplyCode &&
        createPortal(
          <div
            ref={selectionPopoverRef}
            className="fixed z-[10001] flex max-h-[260px] w-[220px] flex-col border border-paper bg-ink p-2 shadow-lg"
            style={{
              left: selectionPopover.left,
              top: selectionPopover.top,
            }}
            role="dialog"
            aria-label="Tag selected text with a code"
          >
            <input
              autoFocus
              type="text"
              value={popoverFilter}
              onChange={(e) => setPopoverFilter(e.target.value)}
              onMouseDown={(e) => e.stopPropagation()}
              placeholder="Search codes..."
              className="mb-1.5 border border-paper bg-white/5 px-2 py-1 text-xs text-paper placeholder:text-paper/40 focus:outline-none focus:ring-1 focus:ring-paper"
            />
            <div className="flex flex-col gap-1 overflow-y-auto">
              {filteredPopoverCodes.length === 0 ? (
                <div className="px-1 py-1 text-xs text-paper/50">No matching codes</div>
              ) : (
                filteredPopoverCodes.map((code) => (
                  <button
                    key={code}
                    type="button"
                    className="flex items-center gap-1.5 truncate border border-transparent px-1.5 py-1 text-left text-xs transition-colors hover:border-paper hover:bg-white/10"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={handleApplyCodeClick(code)}
                    title={code}
                  >
                    <span
                      className="h-2.5 w-2.5 shrink-0"
                      style={{ backgroundColor: getCodeColor(code) }}
                    />
                    <span className="truncate">{code}</span>
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
