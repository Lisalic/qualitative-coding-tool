// Utility functions for coding operations

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
  const codes = new Set();
  parsedCoding.forEach((post) => {
    post.codeEvidence.forEach(({ code }) => codes.add(code));
  });
  return Array.from(codes).sort();
};

// Get filtered coding data based on selected filter codes
export const getFilteredCoding = (parsedCoding, selectedFilterCodes) => {
  if (selectedFilterCodes.length === 0) return parsedCoding;
  return parsedCoding.filter((post) =>
    post.codeEvidence.some((ev) => selectedFilterCodes.includes(ev.code)),
  );
};

// Parse coding data from raw text content
export const parseCodingData = (content) => {
  const lines = content.split("\n");
  const parsed = [];
  let currentPost = null;

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("POST_ID:")) {
      if (currentPost) {
        parsed.push(currentPost);
      }
      currentPost = {
        postId: trimmed.replace("POST_ID:", "").trim(),
        codeEvidence: [],
      };
    } else if (trimmed.startsWith("CODE:") && currentPost) {
      // Parse "CODE: [code_name] - EVIDENCE: [text1]§[text2]§[text3]"
      const codeMatch = trimmed.match(/^CODE:\s*(.+?)\s*-\s*EVIDENCE:\s*(.+)$/);
      if (codeMatch) {
        const code = codeMatch[1].trim();
        const evidenceString = codeMatch[2].trim();
        // Split evidence on § separator and create separate entries for each snippet
        const evidenceSnippets = evidenceString
          .split("§")
          .map((s) => s.trim())
          .filter((s) => s);
        evidenceSnippets.forEach((evidence) => {
          currentPost.codeEvidence.push({ code, evidence });
        });
      }
    } else if (trimmed.startsWith("CODES:") && currentPost) {
      // Backward compatibility: handle old format
      const codesStr = trimmed.replace("CODES:", "").trim();
      const codes = codesStr
        .split(",")
        .map((code) => code.trim())
        .filter((code) => code);
      // For old format, add codes without evidence
      codes.forEach((code) => {
        currentPost.codeEvidence.push({ code, evidence: "" });
      });
    }
  }

  if (currentPost) {
    parsed.push(currentPost);
  }

  console.log("Parsed coding data:", parsed);
  return parsed;
};
