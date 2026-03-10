import { useState, useEffect, useRef } from "react";

// Component for highlighted content with margin brackets
const HighlightedContent = ({ content, codeEvidence, getCodeColor }) => {
  const containerRef = useRef(null);
  const marginRef = useRef(null);
  const [lines, setLines] = useState([]);
  const [tooltip, setTooltip] = useState(null); // { codes: [...], x, y }

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
          left: index * 8,
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

  const showCodeTooltip = (e, codes) => {
    setTooltip({ codes, x: e.clientX, y: e.clientY });
  };

  const moveTooltip = (e) => {
    setTooltip((prev) =>
      prev ? { ...prev, x: e.clientX, y: e.clientY } : null,
    );
  };

  const hideTooltip = () => setTooltip(null);

  if (!content || !codeEvidence.length) return <span>{content}</span>;

  // Find all evidence matches with their positions
  const intervals = [];
  codeEvidence
    .filter(({ evidence }) => evidence)
    .forEach(({ code, evidence }) => {
      const cleanEvidence = evidence
        .replace(/^["']|["']$/g, "")
        .replace(/\s+/g, " ")
        .trim();

      let searchIndex = 0;
      while (true) {
        const index = content.indexOf(cleanEvidence, searchIndex);
        if (index === -1) break;

        intervals.push({
          start: index,
          end: index + cleanEvidence.length,
          code,
          evidence: cleanEvidence,
          length: cleanEvidence.length,
        });
        searchIndex = index + 1;
      }
    });

  if (intervals.length === 0) return <span>{content}</span>;

  // Sort intervals by start position
  intervals.sort((a, b) => a.start - b.start);

  // Group overlapping intervals by their text segment
  const segments = [];
  intervals.forEach((interval) => {
    const overlapping = segments.find(
      (seg) => seg.start < interval.end && seg.end > interval.start,
    );
    if (overlapping) {
      overlapping.start = Math.min(overlapping.start, interval.start);
      overlapping.end = Math.max(overlapping.end, interval.end);
      overlapping.codes.add(interval.code);
    } else {
      segments.push({
        start: interval.start,
        end: interval.end,
        codes: new Set([interval.code]),
      });
    }
  });

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
        onMouseEnter={(e) => showCodeTooltip(e, codes)}
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
        <div className="text-area" style={{ flex: 1, padding: "10px" }}>
          {elements}
        </div>
        <div
          className="coding-margin"
          ref={marginRef}
          style={{ width: "60px", position: "relative", marginLeft: "10px" }}
        >
          {lines.map((line, idx) => (
            <div
              key={idx}
              className="margin-line"
              style={{
                position: "absolute",
                width: "4px",
                height: `${line.height}px`,
                top: `${line.top}px`,
                left: `${line.left}px`,
                backgroundColor: line.color,
                borderRadius: "2px",
                cursor: "pointer",
              }}
              onMouseEnter={(e) => showCodeTooltip(e, [line.code])}
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
              style={{ display: "flex", alignItems: "center", marginBottom: 4 }}
            >
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
          ))}
        </div>
      )}
    </>
  );
};

export default HighlightedContent;
