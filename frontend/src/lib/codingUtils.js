// Utility functions for coding operations

const POST_ID_LINE_RE = /^(?:POST[\s_-]*ID)\s*:\s*(.+)$/i;
const POST_ID_CODE_EVIDENCE_LINE_RE =
  /^(?:POST[\s_-]*ID)\s*:\s*(.+?)\s*(?:-|–|—)?\s*CODE\s*:\s*(.+?)\s*(?:-|–|—)\s*EVIDENCE\s*:\s*(.+?)(?:\s*(?:-|–|—)\s*NOTES\s*:\s*(.+))?$/i;
const CODE_EVIDENCE_LINE_RE =
  /^CODE\s*:\s*(.+?)\s*(?:-|–|—)\s*EVIDENCE\s*:\s*(.+?)(?:\s*(?:-|–|—)\s*NOTES\s*:\s*(.+))?$/i;
const CODE_LINE_RE = /^CODE\s*:\s*(.+)$/i;
const EVIDENCE_LINE_RE = /^EVIDENCE\s*:\s*(.+)$/i;
const NOTES_LINE_RE = /^NOTES\s*:\s*(.+)$/i;
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

/** Deep clone codebook tree (family_name, content, codes[].code_name, codes[].content). */
export const cloneCodebookTree = (tree) => {
  if (!Array.isArray(tree)) return [];
  return tree.map((family) => ({
    family_name:
      typeof family?.family_name === "string" ? family.family_name : "",
    content: typeof family?.content === "string" ? family.content : "",
    codes: (Array.isArray(family?.codes) ? family.codes : []).map((code) => ({
      code_name: typeof code?.code_name === "string" ? code.code_name : "",
      content: typeof code?.content === "string" ? code.content : "",
    })),
  }));
};

/**
 * Serialize tree to markdown matching backend/scripts/display_codebook.py parse_codebook_to_json input.
 */
export const serializeCodebookTreeToText = (tree) => {
  if (!Array.isArray(tree) || tree.length === 0) return "";

  const lines = [];
  for (const family of tree) {
    const fname = String(family?.family_name ?? "").trim() || "Unnamed family";
    lines.push(`### Code Family: ${fname}`);

    const fc = String(family?.content ?? "").trimEnd();
    if (fc) {
      for (const part of fc.split("\n")) {
        lines.push(part);
      }
    }

    const codes = Array.isArray(family?.codes) ? family.codes : [];
    for (const code of codes) {
      const cname = String(code?.code_name ?? "").trim();
      lines.push(`#### Code Name: ${cname}`);
      const cc = String(code?.content ?? "").trimEnd();
      if (cc) {
        for (const part of cc.split("\n")) {
          lines.push(part);
        }
      }
    }

    lines.push("");
  }

  return lines.join("\n").trim();
};

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
      line.replace(
        /^\s*[-*+]\s*(?=(?:POST[\s_-]*ID|CODE|EVIDENCE|NOTES)\s*:)/i,
        "",
      ),
    )
    .map(cleanInlineText)
    .filter(Boolean)
    .filter((line) => /^(?:POST[\s_-]*ID|CODE|EVIDENCE|NOTES)\s*:/i.test(line));
};

const splitEvidenceSnippets = (evidenceText) => {
  const raw = String(evidenceText || "");
  const quotedMatches = Array.from(raw.matchAll(QUOTED_EVIDENCE_RE)).map((m) =>
    normalizeEvidenceText(m[1]),
  );

  if (quotedMatches.length > 0) {
    return quotedMatches.filter(Boolean);
  }

  return raw
    .split("§")
    .map((snippet) => normalizeEvidenceText(snippet))
    .filter(Boolean);
};

const appendCodeEvidenceEntries = (
  targetCodeEvidence,
  codeValue,
  evidenceValue,
  notesValue = "",
) => {
  const code = cleanInlineText(codeValue);
  const evidenceSnippets = splitEvidenceSnippets(evidenceValue);
  const notes = cleanInlineText(notesValue);

  if (!code || evidenceSnippets.length === 0) return;

  evidenceSnippets.forEach((evidence) => {
    targetCodeEvidence.push(
      notes ? { code, evidence, notes } : { code, evidence },
    );
  });
};

const formatEvidenceBlock = (value) => {
  const segments = splitEvidenceSnippets(value)
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
  let pendingCode = "";
  let pendingNotes = "";

  const flushCurrentPost = () => {
    if (
      currentPost &&
      currentPost.postId &&
      currentPost.codeEvidence.length > 0
    ) {
      parsed.push(currentPost);
    }
    currentPost = null;
    pendingCode = "";
    pendingNotes = "";
  };

  for (const line of lines) {
    const inlinePostCodeEvidenceMatch = line.match(
      POST_ID_CODE_EVIDENCE_LINE_RE,
    );
    if (inlinePostCodeEvidenceMatch) {
      flushCurrentPost();

      const postId = cleanInlineText(inlinePostCodeEvidenceMatch[1]);

      if (!postId) continue;

      currentPost = {
        postId,
        codeEvidence: [],
      };

      appendCodeEvidenceEntries(
        currentPost.codeEvidence,
        inlinePostCodeEvidenceMatch[2],
        inlinePostCodeEvidenceMatch[3],
        inlinePostCodeEvidenceMatch[4],
      );

      pendingCode = "";
      pendingNotes = "";
      continue;
    }

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
      appendCodeEvidenceEntries(
        currentPost.codeEvidence,
        codeEvidenceMatch[1],
        codeEvidenceMatch[2],
        codeEvidenceMatch[3],
      );
      pendingCode = "";
      pendingNotes = "";
      continue;
    }

    const codeOnlyMatch = line.match(CODE_LINE_RE);
    if (codeOnlyMatch) {
      pendingCode = cleanInlineText(codeOnlyMatch[1]);
      pendingNotes = "";
      continue;
    }

    const notesOnlyMatch = line.match(NOTES_LINE_RE);
    if (notesOnlyMatch && pendingCode) {
      pendingNotes = cleanInlineText(notesOnlyMatch[1]);
      continue;
    }

    const evidenceOnlyMatch = line.match(EVIDENCE_LINE_RE);
    if (evidenceOnlyMatch && pendingCode) {
      appendCodeEvidenceEntries(
        currentPost.codeEvidence,
        pendingCode,
        evidenceOnlyMatch[1],
        pendingNotes,
      );
      pendingCode = "";
      pendingNotes = "";
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
        return { code, evidence, notes };
      })
      .filter(Boolean);

    if (!postId || formattedEntries.length === 0) return;

    outLines.push(`POST_ID: ${postId}`);
    formattedEntries.forEach(({ code, evidence, notes }) => {
      outLines.push(`CODE: ${code}`);
      if (notes) {
        outLines.push(`NOTES: ${notes}`);
      }
      outLines.push(`EVIDENCE: ${evidence}`);
    });
    outLines.push("");
  });

  return outLines.join("\n").trim();
};
