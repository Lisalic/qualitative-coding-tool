export const cloneParsedCodingRows = (rows = []) =>
  (Array.isArray(rows) ? rows : []).map((row) => ({
    postId: String(row?.postId || ""),
    codeEvidence: (Array.isArray(row?.codeEvidence) ? row.codeEvidence : []).map((entry) => ({
      code: String(entry?.code || ""),
      evidence: String(entry?.evidence || ""),
      notes: String(entry?.notes || ""),
    })),
  }));

export const normalizeParsedCodingRows = (rows = []) => {
  if (!Array.isArray(rows) || rows.length === 0) {
    return { ok: false, error: "Cannot save an empty coding table." };
  }

  const normalizedRows = [];

  for (let rowIndex = 0; rowIndex < rows.length; rowIndex += 1) {
    const row = rows[rowIndex];
    const postId = String(row?.postId || "").trim();

    if (!postId) {
      return {
        ok: false,
        error: `Entry ${rowIndex + 1} is missing a Post ID.`,
      };
    }

    const codeEvidenceInput = Array.isArray(row?.codeEvidence) ? row.codeEvidence : [];
    if (codeEvidenceInput.length === 0) {
      return {
        ok: false,
        error: `Entry ${rowIndex + 1} must include at least one code and evidence pair.`,
      };
    }

    const normalizedCodeEvidence = [];
    for (let entryIndex = 0; entryIndex < codeEvidenceInput.length; entryIndex += 1) {
      const entry = codeEvidenceInput[entryIndex] || {};
      const code = String(entry?.code || "").trim();
      const evidence = String(entry?.evidence || "").trim();
      const notes = String(entry?.notes || "").trim();

      if (!code && !evidence && !notes) continue;
      if (!code || !evidence) {
        return {
          ok: false,
          error: `Entry ${rowIndex + 1}, code/evidence row ${entryIndex + 1} must include both code and evidence.`,
        };
      }

      normalizedCodeEvidence.push(notes ? { code, evidence, notes } : { code, evidence });
    }

    if (normalizedCodeEvidence.length === 0) {
      return {
        ok: false,
        error: `Entry ${rowIndex + 1} must include at least one complete code and evidence pair.`,
      };
    }

    normalizedRows.push({ postId, codeEvidence: normalizedCodeEvidence });
  }

  return { ok: true, rows: normalizedRows };
};

export const extractApiErrorMessage = async (response, fallbackMessage) => {
  let message = fallbackMessage;
  try {
    const payload = await response.json();
    message = payload?.error || payload?.detail || payload?.message || message;
  } catch {
    try {
      const textPayload = await response.text();
      if (textPayload) message = textPayload;
    } catch {
      // Keep fallback message.
    }
  }
  return String(message || fallbackMessage);
};
