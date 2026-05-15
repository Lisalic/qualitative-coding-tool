import { useCallback, useMemo } from "react";
import {
  getFilteredCoding,
  getPostDataById,
  getUniqueCodes,
} from "../../lib/codingUtils";

export default function useCodingTableData({
  parsedCoding,
  editableParsedCoding,
  isEditMode,
  onParsedCodingChange,
  codebookTree,
  editableCodebookTree,
  selectedFilterCodes,
  postContents,
}) {
  const uniqueCodes = useMemo(() => getUniqueCodes(parsedCoding), [parsedCoding]);

  const effectiveCodebookTree =
    isEditMode && Array.isArray(editableCodebookTree)
      ? editableCodebookTree
      : codebookTree;

  const codebookCodes = useMemo(() => {
    if (!Array.isArray(effectiveCodebookTree)) return [];

    const codes = [];
    effectiveCodebookTree.forEach((family) => {
      const familyCodes = Array.isArray(family?.codes) ? family.codes : [];
      familyCodes.forEach((entry) => {
        if (typeof entry === "string" && entry.trim()) {
          codes.push(entry.trim());
          return;
        }
        if (entry && typeof entry.code_name === "string" && entry.code_name) {
          codes.push(entry.code_name.trim());
        }
      });
    });

    return Array.from(new Set(codes)).sort((a, b) => a.localeCompare(b));
  }, [effectiveCodebookTree]);

  const codeFieldOptions = useMemo(
    () =>
      Array.from(new Set([...(uniqueCodes || []), ...(codebookCodes || [])])).sort(
        (a, b) => a.localeCompare(b),
      ),
    [uniqueCodes, codebookCodes],
  );

  const filteredCoding = useMemo(
    () =>
      isEditMode
        ? parsedCoding
        : getFilteredCoding(parsedCoding, selectedFilterCodes),
    [parsedCoding, selectedFilterCodes, isEditMode],
  );

  const rowsForRender = useMemo(
    () =>
      filteredCoding
        .map((item, filteredIndex) => {
          const sourceIndex = parsedCoding.indexOf(item);
          const editableItem =
            Array.isArray(editableParsedCoding) && sourceIndex >= 0
              ? editableParsedCoding[sourceIndex]
              : null;
          const readOnlyCodeEvidence =
            !isEditMode && selectedFilterCodes.length > 0
              ? item.codeEvidence.filter((ev) =>
                  selectedFilterCodes.includes(ev.code),
                )
              : item.codeEvidence;
          const editCodeEvidence = Array.isArray(editableItem?.codeEvidence)
            ? editableItem.codeEvidence
            : [];
          const notesByCode = readOnlyCodeEvidence.reduce((acc, entry) => {
            const code = String(entry?.code || "").trim();
            const notes = String(entry?.notes || "").trim();
            if (!code || !notes) return acc;
            if (!acc[code]) acc[code] = new Set();
            acc[code].add(notes);
            return acc;
          }, {});
          const postData = getPostDataById(postContents, item.postId);
          const postTitle = postData?.title || "Title not found";
          const postContent = postData?.content;
          const rowKey = `${sourceIndex}-${filteredIndex}`;
          const codeDatalistId = `code-options-${rowKey}`;
          const editCodes = Array.from(
            new Set(
              editCodeEvidence
                .map((entry) => String(entry?.code || "").trim())
                .filter(Boolean),
            ),
          );

          return {
            item,
            editableItem,
            sourceIndex,
            rowKey,
            readOnlyCodeEvidence,
            editCodeEvidence,
            notesByCode,
            postTitle,
            postContent,
            codeDatalistId,
            editCodes,
          };
        })
        .filter((row) => row.sourceIndex >= 0),
    [
      filteredCoding,
      parsedCoding,
      editableParsedCoding,
      isEditMode,
      selectedFilterCodes,
      postContents,
    ],
  );

  const updateRowPostId = useCallback(
    (sourceIndex, value) => {
      if (!isEditMode || typeof onParsedCodingChange !== "function") return;
      const currentRows = Array.isArray(editableParsedCoding)
        ? editableParsedCoding
        : [];
      onParsedCodingChange(
        currentRows.map((row, index) =>
          index === sourceIndex ? { ...row, postId: value } : row,
        ),
      );
    },
    [isEditMode, onParsedCodingChange, editableParsedCoding],
  );

  const updateRowCodeEvidenceField = useCallback(
    (sourceIndex, entryIndex, field, value) => {
      if (!isEditMode || typeof onParsedCodingChange !== "function") return;
      const currentRows = Array.isArray(editableParsedCoding)
        ? editableParsedCoding
        : [];
      onParsedCodingChange(
        currentRows.map((row, index) => {
          if (index !== sourceIndex) return row;
          const nextCodeEvidence = (
            Array.isArray(row?.codeEvidence) ? row.codeEvidence : []
          ).map((entry, idx) =>
            idx === entryIndex ? { ...entry, [field]: value } : entry,
          );
          return { ...row, codeEvidence: nextCodeEvidence };
        }),
      );
    },
    [isEditMode, onParsedCodingChange, editableParsedCoding],
  );

  const addRowCodeEvidence = useCallback(
    (sourceIndex) => {
      if (!isEditMode || typeof onParsedCodingChange !== "function") return;
      const currentRows = Array.isArray(editableParsedCoding)
        ? editableParsedCoding
        : [];
      onParsedCodingChange(
        currentRows.map((row, index) =>
          index === sourceIndex
            ? {
                ...row,
                codeEvidence: [
                  ...(Array.isArray(row?.codeEvidence) ? row.codeEvidence : []),
                  { code: "", evidence: "", notes: "" },
                ],
              }
            : row,
        ),
      );
    },
    [isEditMode, onParsedCodingChange, editableParsedCoding],
  );

  const appendCodeEvidenceWithText = useCallback(
    (sourceIndex, evidenceText) => {
      if (!isEditMode || typeof onParsedCodingChange !== "function") return;
      const text = String(evidenceText ?? "");
      if (!text.trim()) return;
      const currentRows = Array.isArray(editableParsedCoding)
        ? editableParsedCoding
        : [];
      onParsedCodingChange(
        currentRows.map((row, index) =>
          index === sourceIndex
            ? {
                ...row,
                codeEvidence: [
                  ...(Array.isArray(row?.codeEvidence) ? row.codeEvidence : []),
                  { code: "", evidence: text, notes: "" },
                ],
              }
            : row,
        ),
      );
    },
    [isEditMode, onParsedCodingChange, editableParsedCoding],
  );

  const removeRowCodeEvidence = useCallback(
    (sourceIndex, entryIndex) => {
      if (!isEditMode || typeof onParsedCodingChange !== "function") return;
      const currentRows = Array.isArray(editableParsedCoding)
        ? editableParsedCoding
        : [];
      onParsedCodingChange(
        currentRows.map((row, index) => {
          if (index !== sourceIndex) return row;
          const codeEvidence = Array.isArray(row?.codeEvidence)
            ? row.codeEvidence
            : [];
          return {
            ...row,
            codeEvidence: codeEvidence.filter((_, idx) => idx !== entryIndex),
          };
        }),
      );
    },
    [isEditMode, onParsedCodingChange, editableParsedCoding],
  );

  return {
    codeFieldOptions,
    rowsForRender,
    updateRowPostId,
    updateRowCodeEvidenceField,
    addRowCodeEvidence,
    appendCodeEvidenceWithText,
    removeRowCodeEvidence,
  };
}
