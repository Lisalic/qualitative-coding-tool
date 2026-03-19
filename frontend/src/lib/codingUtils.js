// Utility functions for coding operations

const POST_ID_LINE_RE = /^(?:POST[\s_-]*ID)\s*:\s*(.+)$/i;
const CODE_EVIDENCE_LINE_RE =
  /^CODE\s*:\s*(.+?)\s*(?:-|–|—)\s*EVIDENCE\s*:\s*(.+?)(?:\s*(?:-|–|—)\s*NOTES\s*:\s*(.+))?$/i;
const QUOTED_EVIDENCE_RE = /"([^"\n]+)"/g;

const cleanInlineText = (value) => {
  if (!value) return "";
  return String(value)
    .replace(/\u201c|\u201d/g, '"')
    .replace(/\u2018|\u2019/g, "'")
    .replace(/\*\*/g, "")
    .replace(/__/g, "")
    .replace(/`/g, "")
    .replace(/\[(.*?)\]\((.*?)\)/g, "$1")
    .replace(/^\s*[-*+]\s*/, "")
    .replace(/\s+/g, " ")
    .trim();
};

export const normalizeEvidenceText = (value) =>
  cleanInlineText(value)
    .replace(/^['"]|['"]$/g, "")
    .trim();

const preprocessCodingLines = (content) => {
  if (typeof content !== "string") return [];

  return content
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .filter((line) => !/^```/.test(line))
    .filter((line) => !/^(?:-{3,}|\*{3,}|_{3,})$/.test(line))
    .map((line) => line.replace(/^#{1,6}\s*/, ""))
    .map((line) =>
      line.replace(/^\s*[-*+]\s*(?=(?:POST[\s_-]*ID|CODE)\s*:)/i, ""),
    )
    .map(cleanInlineText)
    .filter(Boolean)
    .filter((line) => /^(?:POST[\s_-]*ID|CODE)\s*:/i.test(line));
};

const splitEvidenceSnippets = (evidenceText) =>
  (() => {
    const raw = String(evidenceText || "");
    const quotedMatches = Array.from(raw.matchAll(QUOTED_EVIDENCE_RE)).map(
      (m) => normalizeEvidenceText(m[1]),
    );
    if (quotedMatches.length > 0) {
      return quotedMatches.filter(Boolean);
    }

    return raw
      .split("§")
      .map((snippet) => normalizeEvidenceText(snippet))
      .filter(Boolean);
  })();

const formatEvidenceBlock = (value) => {
  const raw = String(value || "");
  const quotedMatches = Array.from(raw.matchAll(QUOTED_EVIDENCE_RE)).map((m) =>
    normalizeEvidenceText(m[1]),
  );

  const segments = (
    quotedMatches.length > 0
      ? quotedMatches
      : raw.split("§").map((snippet) => normalizeEvidenceText(snippet))
  )
    .map((segment) => segment.replace(/"/g, "'"))
    .filter(Boolean);

  return segments.map((segment) => `"${segment}"`).join("§");
};

// Color assignment for codes
export const getCodeColor = (code) => {
  // Simple hash function for consistent colors
  let hash = 0;
  for (let i = 0; i < code.length; i++) {
    hash = code.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;
  // Use higher saturation and varied lightness for better distinction
  const saturation = 85;
  const lightness = 55 + (Math.abs(hash) % 20); // Vary lightness between 55-75%
  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
};

// Get all unique codes for legend
export const getUniqueCodes = (parsedCoding) => {
  if (!Array.isArray(parsedCoding)) return [];
  const codes = new Set();
  parsedCoding.forEach((post) => {
    (post.codeEvidence || []).forEach(({ code }) => {
      if (code) codes.add(code);
    });
  });
  return Array.from(codes).sort();
};

// Get filtered coding data based on selected filter codes
export const getFilteredCoding = (parsedCoding, selectedFilterCodes) => {
  if (!Array.isArray(parsedCoding)) return [];
  if (!selectedFilterCodes || selectedFilterCodes.length === 0) {
    return parsedCoding;
  }
  const filterSet = new Set(selectedFilterCodes);
  return parsedCoding.filter((post) =>
    (post.codeEvidence || []).some((ev) => filterSet.has(ev.code)),
  );
};

// Case-insensitive lookup helper for post contents mapped by id
export const getPostDataById = (postContents, postId) => {
  if (!postContents || !postId) return null;
  const postIdLower = String(postId).toLowerCase();
  const matchingKey = Object.keys(postContents).find(
    (key) => key.toLowerCase() === postIdLower,
  );
  return matchingKey ? postContents[matchingKey] : null;
};

// Parse coding data from raw text content
export const parseCodingData = (content) => {
  const lines = preprocessCodingLines(content);
  if (lines.length === 0) return [];

  const parsed = [];
  let currentPost = null;

  const flushCurrentPost = () => {
    if (
      currentPost &&
      currentPost.postId &&
      currentPost.codeEvidence.length > 0
    ) {
      parsed.push(currentPost);
    }
    currentPost = null;
  };

  for (const line of lines) {
    const postMatch = line.match(POST_ID_LINE_RE);
    if (postMatch) {
      flushCurrentPost();

      const postId = cleanInlineText(postMatch[1]);
      if (!postId) continue;

      currentPost = {
        postId,
        codeEvidence: [],
      };
      continue;
    }

    if (!currentPost) continue;

    const codeEvidenceMatch = line.match(CODE_EVIDENCE_LINE_RE);
    if (codeEvidenceMatch) {
      const code = cleanInlineText(codeEvidenceMatch[1]);
      const evidenceSnippets = splitEvidenceSnippets(codeEvidenceMatch[2]);
      const notes = cleanInlineText(codeEvidenceMatch[3]);
      if (code && evidenceSnippets.length > 0) {
        evidenceSnippets.forEach((evidence) => {
          currentPost.codeEvidence.push(
            notes ? { code, evidence, notes } : { code, evidence },
          );
        });
      }
    }
  }

  flushCurrentPost();

  return parsed;
};

// Serialize parsed coding rows back into canonical text format
export const formatCodingData = (parsedCoding) => {
  if (!Array.isArray(parsedCoding)) return "";

  const outLines = [];

  parsedCoding.forEach((post) => {
    const postId = cleanInlineText(post?.postId);
    const codeEvidence = Array.isArray(post?.codeEvidence)
      ? post.codeEvidence
      : [];

    const formattedEntries = codeEvidence
      .map((entry) => {
        const code = cleanInlineText(entry?.code);
        const evidence = formatEvidenceBlock(entry?.evidence);
        const notes = cleanInlineText(entry?.notes);
        if (!code || !evidence) return null;
        return notes
          ? `CODE: ${code} - EVIDENCE: ${evidence} - NOTES: ${notes}`
          : `CODE: ${code} - EVIDENCE: ${evidence}`;
      })
      .filter(Boolean);

    if (!postId || formattedEntries.length === 0) return;

    outLines.push(`POST_ID: ${postId}`);
    outLines.push(...formattedEntries);
    outLines.push("");
  });

  return outLines.join("\n").trim();
};
