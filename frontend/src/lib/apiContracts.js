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
  filter:
    "Act as a qualitative research assistant tasked with cleaning raw data transcripts for analysis. For each input item, decide whether it should be kept or removed. Apply these rules: remove spam/automated posts, remove obvious duplicates, and remove non-topical noise. Keep authentic human discussion and on-topic content.",
  generate:
    "You are a codebook generator. Read representative dataset excerpts and propose a concise codebook of [topic]. Keep entries concise and focused; do not add unrelated commentary.\nResearch Context: These are excerpts from [e.g., reddit stories about bullying]. Specific Focus: Please generate codes specifically related to [e.g., retrospective bullying experiences.]",
  apply:
    "You are a coding assistant. Given a codebook and an input item, decide which code(s) from the codebook apply and provide a one-sentence justification. Focus on selecting the single best code when applicable; do not invent new codes. Keep responses concise.",
};

export class MissingFieldsError extends Error {
  constructor(missing, flow) {
    super(`Missing required fields for ${flow}: ${missing.join(", ")}`);
    this.name = "MissingFieldsError";
    this.missing = missing;
    this.flow = flow;
  }
}

const PROJ_SCHEMA_RE = /^proj_[A-Za-z0-9_]+$/;

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
  assertRequired({ apiKey }, "recode-items");
  if (!Array.isArray(itemIds) || itemIds.length === 0) {
    throw new MissingFieldsError(["itemIds"], "recode-items");
  }

  const payload = { api_key: apiKey, item_ids: itemIds };
  if (!isBlank(model)) payload.model = model;
  if (!isBlank(methodology)) payload.methodology = methodology;
  return payload;
}

/**
 * Build the JSON body for POST /api/filter-preview/.
 * Mirrors `FilterPreviewRequest` in `backend/app/api/schemas.py`.
 *
 * `decidedPostIds`/`decidedCommentIds` are the rows the user has already
 * included or excluded in the filter editor. They are sent so the server
 * can drop them from the candidate pool before sampling -- which is what
 * makes re-running the tool propose new rows rather than the same ones.
 * They are legitimately empty on a first run, so unlike the other
 * builders they are not `assertRequired`.
 */
export function buildFilterPreviewPayload({
  apiKey,
  database,
  model,
  prompt,
  filterTags,
  minWords,
  samplePercentage,
  contentScope,
  decidedPostIds,
  decidedCommentIds,
}) {
  assertRequired({ apiKey, database, model }, "filter-preview");
  const normalizedDatabase = assertProjSchema(
    database,
    "database",
    "filter-preview",
  );

  const payload = {
    api_key: apiKey,
    database: normalizedDatabase,
    model,
    sample_percentage: clampPct(samplePercentage),
    decided_post_ids: decidedPostIds || [],
    decided_comment_ids: decidedCommentIds || [],
  };

  if (!isBlank(prompt)) payload.prompt = prompt;
  if (!isBlank(filterTags)) payload.filter_tags = filterTags.trim();
  if (!isBlank(contentScope)) payload.content_scope = contentScope;

  const mw = Number(minWords);
  if (Number.isFinite(mw) && mw > 0) payload.min_words = mw;

  return payload;
}

/**
 * Build the JSON body for POST /api/filtered-data/manual.
 * Mirrors `ManualFilterRequest` in `backend/app/api/schemas.py`.
 *
 * No `apiKey` or `model`: submitting the editor's selection creates the
 * artifact with no LLM call, whatever role the AI preview tool played in
 * assembling that selection.
 */
export function buildManualFilterPayload({
  database,
  name,
  description,
  projectId,
  postIds,
  commentIds,
}) {
  assertRequired({ database, name }, "manual-filter");
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
  };
  if (!isBlank(description)) payload.description = description;
  if (projectId !== undefined && projectId !== null && projectId !== "") {
    payload.project_id = Number(projectId);
  }
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
 */
export function buildManualCodebookPayload({
  database,
  name,
  description,
  projectId,
  codes,
}) {
  assertRequired({ database, name }, "manual-codebook");
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
  };
  if (!isBlank(description)) payload.description = description;
  if (projectId !== undefined && projectId !== null && projectId !== "") {
    payload.project_id = Number(projectId);
  }
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
  assertRequired({ database, codebook, reportName }, "manual-coding");
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
  if (projectId !== undefined && projectId !== null && projectId !== "") {
    payload.project_id = Number(projectId);
  }
  return payload;
}
