import { useState, useEffect, useRef } from "react";
import { normalizeEvidenceText } from "../lib/codingUtils";

const escapeRegExp = (value) =>
  String(value || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

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

const buildEvidenceIntervals = (content, codeEvidence) => {
  const intervals = [];

  (codeEvidence || [])
    .filter(({ evidence, code }) => evidence && code)
    .forEach(({ code, evidence, notes }) => {
      const cleanEvidence = normalizeEvidenceText(evidence);
      if (!cleanEvidence) return;

      const cleanNotes = String(notes || "").trim();

      let foundAny = false;
      let searchIndex = 0;
      while (true) {
        const index = content.indexOf(cleanEvidence, searchIndex);
        if (index === -1) break;

        foundAny = true;
        intervals.push({
          start: index,
          end: index + cleanEvidence.length,
          code,
          evidence: cleanEvidence,
          notes: cleanNotes,
          length: cleanEvidence.length,
        });
        searchIndex = index + 1;
      }

      if (!foundAny) {
        const relaxedPattern = escapeRegExp(cleanEvidence).replace(
          /\s+/g,
          "\\\\s+",
        );
        const relaxedRegex = new RegExp(relaxedPattern, "gi");
        let match;
        while ((match = relaxedRegex.exec(content)) !== null) {
          intervals.push({
            start: match.index,
            end: match.index + match[0].length,
            code,
            evidence: cleanEvidence,
            notes: cleanNotes,
            length: match[0].length,
          });
          if (match.index === relaxedRegex.lastIndex) {
            relaxedRegex.lastIndex += 1;
          }
        }
      }
    });

  return intervals;
};

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

// Narrow gutter for code stripes (was 28px; keep step proportional so several codes still fit)
const CODING_MARGIN_WIDTH_PX = 18;
const MARGIN_STRIPE_STEP_PX = 4;
const MARGIN_STRIPE_WIDTH_PX = 2;

// Component for highlighted content with margin brackets
const HighlightedContent = ({ content, codeEvidence, getCodeColor }) => {
  const containerRef = useRef(null);
  const marginRef = useRef(null);
  const [lines, setLines] = useState([]);
  const [tooltip, setTooltip] = useState(null); // { codes: [...], notesByCode: { [code]: string[] }, x, y }

  const calculateLines = () => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    const codedSpans = container.querySelectorAll(".coded-span");

    const newLines = [];

    codedSpans.forEach((span) => {
      const codes = span.getAttribute("data-codes").split(",");
      const rect = span.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();

      const top = rect.top - containerRect.top;
      const height = rect.height;

      codes.forEach((code, index) => {
        newLines.push({
          code,
          top,
          height,
          left: index * MARGIN_STRIPE_STEP_PX,
          color: getCodeColor(code),
        });
      });
    });

    setLines(newLines);
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
    window.addEventListener("scroll", hide, true); // capture phase catches inner scrolls
    return () => window.removeEventListener("scroll", hide, true);
  }, [tooltip]);

  const showCodeTooltip = (e, codes, notesByCode = {}) => {
    setTooltip({ codes, notesByCode, x: e.clientX, y: e.clientY });
  };

  const moveTooltip = (e) => {
    setTooltip((prev) =>
      prev ? { ...prev, x: e.clientX, y: e.clientY } : null,
    );
  };

  const hideTooltip = () => setTooltip(null);

  if (!content || !codeEvidence.length) return <span>{content}</span>;

  const intervals = buildEvidenceIntervals(content, codeEvidence);

  if (intervals.length === 0) return <span>{content}</span>;

  const segments = mergeIntervalsToSegments(intervals);
  const notesByCodeLookup = buildNotesByCodeLookup(codeEvidence);

  // Build the content with coded spans
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
        className="coded-span"
        data-codes={codes.join(",")}
        style={{
          position: "relative",
          backgroundColor: "#e0e0e0",
          color: "#000000",
          borderRadius: "2px",
          padding: "1px 2px",
          cursor: "pointer",
        }}
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

  return (
    <>
      <div
        className="highlighted-container"
        ref={containerRef}
        style={{ display: "flex", position: "relative" }}
      >
        <div className="text-area" style={{ flex: 1, padding: "8px 6px 8px 8px" }}>
          {elements}
        </div>
        <div
          className="coding-margin"
          ref={marginRef}
          style={{
            width: `${CODING_MARGIN_WIDTH_PX}px`,
            position: "relative",
            marginLeft: "4px",
            flexShrink: 0,
          }}
        >
          {lines.map((line, idx) => (
            <div
              key={idx}
              className="margin-line"
              style={{
                position: "absolute",
                width: `${MARGIN_STRIPE_WIDTH_PX}px`,
                height: `${line.height}px`,
                top: `${line.top}px`,
                left: `${line.left}px`,
                backgroundColor: line.color,
                borderRadius: "1px",
                cursor: "pointer",
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
          className="robust-tooltip show"
          style={{
            left: tooltip.x + 12,
            top: tooltip.y + 12,
          }}
        >
          <div
            style={{
              fontWeight: 700,
              fontSize: 12,
              marginBottom: 6,
              color: "#aaa",
              textTransform: "uppercase",
              letterSpacing: "0.5px",
            }}
          >
            Codes:
          </div>
          {tooltip.codes.map((code) => (
            <div
              key={code}
              style={{
                display: "flex",
                alignItems: "flex-start",
                marginBottom: 8,
                flexDirection: "column",
                gap: 4,
              }}
            >
              <div style={{ display: "flex", alignItems: "center" }}>
                <div
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: 2,
                    marginRight: 8,
                    flexShrink: 0,
                    backgroundColor: getCodeColor(code),
                  }}
                />
                <span style={{ fontWeight: 600 }}>{code}</span>
              </div>
              {Array.isArray(tooltip.notesByCode?.[code]) &&
                tooltip.notesByCode[code].length > 0 && (
                  <div
                    style={{
                      marginLeft: 18,
                      fontSize: 12,
                      color: "#d0d0d0",
                      lineHeight: 1.35,
                      maxWidth: 260,
                    }}
                  >
                    <div
                      style={{
                        fontWeight: 700,
                        fontSize: 11,
                        color: "#9b9b9b",
                        textTransform: "uppercase",
                        letterSpacing: "0.35px",
                        marginBottom: 2,
                      }}
                    >
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
    </>
  );
};

export default HighlightedContent;
