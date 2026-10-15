/**
 * Single source of truth for the filter/codebook/coding editors' payloads.
 * Each editor imports `EXAMPLE_PROMPTS` and its `buildX` helpers from here
 * instead of building request bodies inline.
 *
 * Each builder's arguments mirror the corresponding Pydantic model in
 * `backend/app/api/schemas.py` (FilterPreviewRequest, ManualFilterRequest,
 * CodebookPreviewRequest, ManualCodebookRequest, ManualCodingRequest,
 * RecodeItemsRequest). When a field is required on the server,
 * `assertRequired` rejects missing values up front so the user sees a
 * clear error instead of a 422 from the backend.
 */

export const EXAMPLE_PROMPTS = {
  filterInclude:
    "Keep authentic human discussion that is on-topic for [subject]. Include posts and comments that reflect a genuine first-person account or opinion, even if brief.",
  filterExclude:
    "Remove spam and automated/bot posts, obvious duplicates, and non-topical noise unrelated to [subject].",
  generate:
    "You are a codebook generator. Read representative dataset excerpts and propose a concise codebook of [topic]. Keep entries concise and focused; do not add unrelated commentary.\nResearch Context: These are excerpts from [e.g., reddit stories about bullying]. Specific Focus: Please generate codes specifically related to [e.g., retrospective bullying experiences.]",
  apply:
    "You are a coding assistant. Given a codebook and an input item, decide which code(s) from the codebook apply and provide a one-sentence justification. Focus on selecting the single best code when applicable; do not invent new codes. Keep responses concise.",
  integrate:
    "Merge codes describing the same concept even if named differently, picking the clearer name and combining their definitions. Keep genuinely distinct codes separate, and carry through a code that appears in only one codebook rather than dropping it.",
};

// What to tell the user for each missing field, keyed on the field's
// leading word (entries like "database (must match proj_<id>)" carry a
// developer note after it). Anything unlisted is shown as written.
const FIELD_HINTS = {
  apiKey: "Set your OpenRouter API key (Set API Key, top right).",
  model: "Choose an AI model.",
  database: "Choose a source database.",
  codebook: "Choose a codebook.",
  codebooks: "Choose at least 2 codebooks.",
  comparisons: "Choose a valid comparison.",
  name: "Enter a name.",
  reportName: "Enter a name.",
  projectId: "Choose a project.",
  itemIds: "Select at least one row.",
  rows: "Keep at least one row.",
  codes: "Add at least one code.",
  "include or exclude criteria": "Describe which rows to keep or skip.",
  "at least one included or excluded row": "Keep or skip at least one row first.",
};

function hintFor(entry) {
  const text = String(entry);
  if (FIELD_HINTS[text]) return FIELD_HINTS[text];
  const head = text.split(/[\s(]/, 1)[0];
  if (FIELD_HINTS[head]) return FIELD_HINTS[head];
  return `${text.charAt(0).toUpperCase()}${text.slice(1)}${/[.!?]$/.test(text) ? "" : "."}`;
}

export class MissingFieldsError extends Error {
  constructor(missing, flow) {
    super(`Missing required fields for ${flow}: ${missing.join(", ")}`);
    this.name = "MissingFieldsError";
    this.missing = missing;
    this.flow = flow;
  }

  /** The same problem in the user's terms -- what to do, not which field
   * name the request builder rejected. Show this; `message` is for logs. */
  get userMessage() {
    return [...new Set(this.missing.map(hintFor))].join(" ");
  }
}

const PROJ_SCHEMA_RE = /^proj_[A-Za-z0-9_]+$/;
const CMP_SCHEMA_RE = /^cmp_[A-Za-z0-9_]+$/;

function isBlank(value) {
  return (
    value === undefined ||
    value === null ||
    (typeof value === "string" && value.trim() === "")
  );
}

function assertRequired(fields, flow) {
  const missing = Object.entries(fields)
    .filter(([, v]) => isBlank(v))
    .map(([k]) => k);
  if (missing.length > 0) throw new MissingFieldsError(missing, flow);
}

function clampPct(value, { min = 1, max = 100, fallback = 100 } = {}) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  if (n < min) return min;
  if (n > max) return max;
  return n;
}

function stripDbSuffix(schema) {
  if (typeof schema !== "string") return schema;
  const trimmed = schema.trim();
  return trimmed.endsWith(".db") ? trimmed.slice(0, -3) : trimmed;
}

function assertProjSchema(schema, field, flow) {
  const normalized = stripDbSuffix(schema);
  if (!PROJ_SCHEMA_RE.test(normalized)) {
    throw new MissingFieldsError(
      [`${field} (must match proj_<id>)`],
      flow,
    );
  }
  return normalized;
}

/**
 * Same shape check as `assertProjSchema`, over a list -- the integrate
 * editor's "which codebooks am I merging" field. Requires at least `min`
 * distinct (post-`.db`-strip) refs, mirroring
 * `schemas._validate_codebook_schema_list`'s dedupe-while-preserving-order
 * and the service layer's "at least two distinct codebooks" guard.
 */
function assertProjSchemaList(list, field, flow, { min = 2 } = {}) {
  const raw = Array.isArray(list) ? list : [];
  const seen = new Set();
  const normalized = [];
  for (const entry of raw) {
    const cleaned = assertProjSchema(entry, field, flow);
    if (seen.has(cleaned)) continue;
    seen.add(cleaned);
    normalized.push(cleaned);
  }
  if (normalized.length < min) {
    throw new MissingFieldsError(
      [`${field} (select at least ${min})`],
      flow,
    );
  }
  return normalized;
}

/**
 * A codebook reference is either a numeric File id or a `proj_<id>`
 * schema name -- both accepted, nothing else. Mirrors
 * `schemas._validate_codebook_ref_value`, and shared by the AI and
 * by-hand coding builders so the two cannot drift.
 */
function assertCodebookRef(codebook, flow) {
  const raw = String(codebook ?? "").trim();
  if (!raw.startsWith("proj_") && !/^\d+$/.test(raw)) {
    throw new MissingFieldsError(
      ["codebook (must be numeric File id or proj_<id> schema)"],
      flow,
    );
  }
  return raw;
}

/**
 * Build the JSON body for POST /api/coding/{ref}/recode. Mirrors
 * `RecodeItemsRequest` -- unlike the flows above, this one is sent as a
 * JSON body (via `requestJson`/`postJsonAndPoll`, not `postForm`), since
 * `itemIds` is a list rather than a flat form field.
 */
export function buildRecodeItemsPayload({ apiKey, itemIds, model, methodology }) {
  assertRequired({ apiKey, model }, "recode-items");
  if (!Array.isArray(itemIds) || itemIds.length === 0) {
    throw new MissingFieldsError(["itemIds"], "recode-items");
  }

  const payload = { api_key: apiKey, item_ids: itemIds, model };
  if (!isBlank(methodology)) payload.methodology = methodology;
  return payload;
}

/**
 * Build the JSON body for POST /api/filter-preview/.
 * Mirrors `FilterPreviewRequest` in `backend/app/api/schemas.py`.
 *
 * The `included*`/`excluded*` id lists are always sent so the server can
 * drop already-decided rows from the candidate pool -- which is what
 * makes re-running the tool propose new rows -- and double as the
 * "similar example" source when `useExamples` is set.
 *
 * When `useExamples` is false, at least one of `includePrompt`,
 * `excludePrompt`, or `filterTags` is required (mirrors the server's
 * `_has_criteria` guard), so a run with nothing to go on fails here
 * with a clear message instead of a 422.
 */
export function buildFilterPreviewPayload({
  apiKey,
  database,
  model,
  includePrompt,
  excludePrompt,
  useExamples,
  filterTags,
  minWords,
  samplePercentage,
  contentScope,
  includedPostIds,
  includedCommentIds,
  excludedPostIds,
  excludedCommentIds,
}) {
  assertRequired({ apiKey, database, model }, "filter-preview");
  const normalizedDatabase = assertProjSchema(
    database,
    "database",
    "filter-preview",
  );

  const hasDecisions =
    (includedPostIds || []).length > 0 ||
    (includedCommentIds || []).length > 0 ||
    (excludedPostIds || []).length > 0 ||
    (excludedCommentIds || []).length > 0;

  if (useExamples) {
    if (!hasDecisions) {
      throw new MissingFieldsError(["at least one included or excluded row"], "filter-preview");
    }
  } else if (isBlank(includePrompt) && isBlank(excludePrompt) && isBlank(filterTags)) {
    throw new MissingFieldsError(["include or exclude criteria"], "filter-preview");
  }

  const payload = {
    api_key: apiKey,
    database: normalizedDatabase,
    model,
    use_examples: !!useExamples,
    sample_percentage: clampPct(samplePercentage),
    included_post_ids: includedPostIds || [],
    included_comment_ids: includedCommentIds || [],
    excluded_post_ids: excludedPostIds || [],
    excluded_comment_ids: excludedCommentIds || [],
  };

  if (!isBlank(includePrompt)) payload.include_prompt = includePrompt;
  if (!isBlank(excludePrompt)) payload.exclude_prompt = excludePrompt;
  if (!isBlank(filterTags)) payload.filter_tags = filterTags.trim();
  if (!isBlank(contentScope)) payload.content_scope = contentScope;

  const mw = Number(minWords);
  if (Number.isFinite(mw) && mw > 0) payload.min_words = Math.ceil(mw);

  return payload;
}

/**
 * Build the JSON body for POST /api/filtered-data/manual.
 * Mirrors `ManualFilterRequest` in `backend/app/api/schemas.py`.
 *
 * No `apiKey` or `model`: submitting the editor's selection creates the
 * artifact with no LLM call, whatever role the AI preview tool played in
 * assembling that selection. `assistRuns` (from
 * `filterEditorState.buildAssistRunsForSubmit`) is the separate C2
 * provenance channel that DOES record which preview run(s) contributed.
 */
export function buildManualFilterPayload({
  database,
  name,
  description,
  projectId,
  postIds,
  commentIds,
  assistRuns,
}) {
  assertRequired({ database, name, projectId }, "manual-filter");
  const normalizedDatabase = assertProjSchema(
    database,
    "database",
    "manual-filter",
  );

  const post_ids = postIds || [];
  const comment_ids = commentIds || [];
  if (post_ids.length === 0 && comment_ids.length === 0) {
    // The server rejects this too; failing here keeps the message
    // actionable instead of surfacing a 422 field path.
    throw new MissingFieldsError(["rows (select at least one)"], "manual-filter");
  }

  const payload = {
    database: normalizedDatabase,
    name: name.trim(),
    post_ids,
    comment_ids,
    assist_runs: assistRuns || [],
  };
  if (!isBlank(description)) payload.description = description;
  payload.project_id = Number(projectId);
  return payload;
}


/**
 * Build the JSON body for POST /api/codebook-preview/.
 * Mirrors `CodebookPreviewRequest` in `backend/app/api/schemas.py`.
 *
 * `existingCodes` is the researcher's live draft, sent so the model is
 * asked for what's missing rather than a fresh taxonomy -- the codebook
 * editor's counterpart to `decided_*_ids` narrowing the filter preview's
 * candidate pool. Legitimately empty on a first pass, so unlike the other
 * fields it is not `assertRequired`.
 *
 * No `name`/`projectId`: a preview creates nothing.
 */
export function buildCodebookPreviewPayload({
  apiKey,
  database,
  model,
  prompt,
  samplePercentage,
  contentScope,
  existingCodes,
}) {
  assertRequired({ apiKey, database, model }, "codebook-preview");
  const normalizedDatabase = assertProjSchema(
    database,
    "database",
    "codebook-preview",
  );

  const payload = {
    api_key: apiKey,
    database: normalizedDatabase,
    model,
    sample_percentage: clampPct(samplePercentage),
    existing_codes: existingCodes || [],
  };

  if (!isBlank(prompt)) payload.prompt = prompt;
  if (!isBlank(contentScope)) payload.content_scope = contentScope;

  return payload;
}

/**
 * Build the JSON body for POST /api/codebook/manual.
 * Mirrors `ManualCodebookRequest` in `backend/app/api/schemas.py`.
 *
 * No `apiKey` or `model`: submitting the editor's draft creates the
 * codebook with no LLM call, whatever role the preview assistant played
 * in assembling that draft. Same reasoning as `buildManualFilterPayload`.
 * `assistRuns` (from `codebookEditorState.buildAssistRunsForSubmit`) is
 * the separate C2 provenance channel that DOES record which preview
 * run(s) contributed.
 */
export function buildManualCodebookPayload({
  database,
  name,
  description,
  projectId,
  codes,
  assistRuns,
}) {
  assertRequired({ database, name, projectId }, "manual-codebook");
  const normalizedDatabase = assertProjSchema(
    database,
    "database",
    "manual-codebook",
  );

  const codeList = Array.isArray(codes) ? codes : [];
  if (codeList.length === 0) {
    // The server rejects this too; failing here keeps the message
    // actionable instead of surfacing a 422 field path.
    throw new MissingFieldsError(["codes (add at least one)"], "manual-codebook");
  }
  const unnamed = codeList.filter((code) => isBlank(code?.name)).length;
  if (unnamed > 0) {
    throw new MissingFieldsError(
      [`${unnamed} code(s) still need a name`],
      "manual-codebook",
    );
  }

  const payload = {
    database: normalizedDatabase,
    name: name.trim(),
    codes: codeList,
    assist_runs: assistRuns || [],
  };
  if (!isBlank(description)) payload.description = description;
  payload.project_id = Number(projectId);
  return payload;
}

/**
 * Build the JSON body for POST /api/integrate-codebook-preview/. Mirrors
 * `IntegrateCodebookPreviewRequest` in `backend/app/api/schemas.py`.
 *
 * No `samplePercentage`/`contentScope`: unlike `buildCodebookPreviewPayload`,
 * this asks the model to merge whole codebooks, not sample raw data, so
 * neither field applies.
 *
 * `comparisons` (optional) are Compare Codebook reports (`cmp_<id>`) the
 * model reads as merge guidance; sent only when non-empty.
 */
export function buildIntegratePreviewPayload({
  apiKey,
  codebooks,
  model,
  prompt,
  existingCodes,
  comparisons,
}) {
  assertRequired({ apiKey, model }, "integrate-codebook-preview");
  const normalizedCodebooks = assertProjSchemaList(
    codebooks,
    "codebooks",
    "integrate-codebook-preview",
  );

  const payload = {
    api_key: apiKey,
    codebooks: normalizedCodebooks,
    model,
    existing_codes: existingCodes || [],
  };
  if (!isBlank(prompt)) payload.prompt = prompt;

  const normalizedComparisons = [];
  for (const ref of comparisons || []) {
    const cleaned = stripDbSuffix(ref);
    if (!CMP_SCHEMA_RE.test(cleaned)) {
      throw new MissingFieldsError(["comparisons (must match cmp_<id>)"], "integrate-codebook-preview");
    }
    if (!normalizedComparisons.includes(cleaned)) normalizedComparisons.push(cleaned);
  }
  if (normalizedComparisons.length > 0) payload.comparisons = normalizedComparisons;

  return payload;
}

/**
 * Build the JSON body for POST /api/codebook/integrate. Mirrors
 * `IntegrateCodebookRequest` in `backend/app/api/schemas.py`.
 *
 * No `apiKey`/`model`: same reasoning as `buildManualCodebookPayload` --
 * submitting the reviewed merge draft creates the codebook with no LLM
 * call, whatever role the integrate assistant played in proposing it.
 * `assistRuns` is the same C2 provenance channel, this time recorded
 * under `ASSIST_STAGE_INTEGRATE` server-side.
 */
export function buildIntegrateCodebookPayload({
  codebooks,
  name,
  description,
  projectId,
  codes,
  assistRuns,
}) {
  assertRequired({ name, projectId }, "integrate-codebook");
  const normalizedCodebooks = assertProjSchemaList(
    codebooks,
    "codebooks",
    "integrate-codebook",
  );

  const codeList = Array.isArray(codes) ? codes : [];
  if (codeList.length === 0) {
    throw new MissingFieldsError(["codes (add at least one)"], "integrate-codebook");
  }
  const unnamed = codeList.filter((code) => isBlank(code?.name)).length;
  if (unnamed > 0) {
    throw new MissingFieldsError(
      [`${unnamed} code(s) still need a name`],
      "integrate-codebook",
    );
  }

  const payload = {
    codebooks: normalizedCodebooks,
    name: name.trim(),
    codes: codeList,
    assist_runs: assistRuns || [],
  };
  if (!isBlank(description)) payload.description = description;
  payload.project_id = Number(projectId);
  return payload;
}

/**
 * Build the JSON body for POST /api/coding/manual.
 * Mirrors `ManualCodingRequest` in `backend/app/api/schemas.py`.
 *
 * No `apiKey`/`model`/`methodology`, because starting a coding artifact
 * by hand calls no model. JSON rather than FormData since it can carry
 * explicit row-id lists.
 */
export function buildManualCodingPayload({
  database,
  codebook,
  reportName,
  description,
  projectId,
  samplePercentage,
  contentScope,
  postIds,
  commentIds,
}) {
  assertRequired({ database, codebook, reportName, projectId }, "manual-coding");
  const normalizedDatabase = assertProjSchema(
    database,
    "database",
    "manual-coding",
  );

  const payload = {
    database: normalizedDatabase,
    codebook: assertCodebookRef(codebook, "manual-coding"),
    report_name: reportName.trim(),
    sample_percentage: clampPct(samplePercentage),
    post_ids: postIds || [],
    comment_ids: commentIds || [],
  };
  if (!isBlank(description)) payload.description = description;
  if (!isBlank(contentScope)) payload.content_scope = contentScope;
  payload.project_id = Number(projectId);
  return payload;
}

/** Mirrors `NewPassword` in backend/app/api/schemas.py (register and reset). */
export const MIN_PASSWORD_LENGTH = 8;
