/**
 * Single source of truth for the three tool-panel flows. The tool panels
 * import `EXAMPLE_PROMPTS` and the `buildXForm` helpers from here instead of
 * building `FormData` objects inline.
 *
 * The shape of each builder's arguments mirrors the corresponding Pydantic
 * model in `backend/app/api/schemas.py` (FilterDataRequest,
 * GenerateCodebookRequest, ApplyCodebookRequest). When a field is required on
 * the server, `assertRequired` rejects missing values up front so the user
 * sees a clear error instead of a 422 from the backend.
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
 * Build the multipart/form-data body for POST /api/filter-data/.
 * Mirrors `FilterDataRequest` in `backend/app/api/schemas.py`.
 */
export function buildFilterDataForm({
  apiKey,
  database,
  name,
  model,
  projectId,
  prompt,
  description,
  minWords,
  samplePercentage,
  filterTags,
  contentScope,
}) {
  assertRequired({ apiKey, database, name, model }, "filter-data");
  const normalizedDatabase = assertProjSchema(
    database,
    "database",
    "filter-data",
  );

  const fd = new FormData();
  fd.append("api_key", apiKey);
  fd.append("database", normalizedDatabase);
  fd.append("name", name.trim());
  fd.append("model", model);
  fd.append("sample_percentage", String(clampPct(samplePercentage)));

  if (projectId !== undefined && projectId !== null && projectId !== "") {
    fd.append("project_id", String(projectId));
  }
  if (!isBlank(prompt)) fd.append("prompt", prompt);
  if (!isBlank(description)) fd.append("description", description);
  if (!isBlank(filterTags)) fd.append("filter_tags", filterTags.trim());
  if (!isBlank(contentScope)) fd.append("content_scope", contentScope);

  const mw = Number(minWords);
  if (Number.isFinite(mw) && mw > 0) fd.append("min_words", String(mw));

  return fd;
}

/**
 * Build the multipart/form-data body for POST /api/generate-codebook/.
 * Mirrors `GenerateCodebookRequest`.
 */
export function buildGenerateCodebookForm({
  apiKey,
  database,
  name,
  model,
  prompt,
  description,
  projectId,
  samplePercentage,
  contentScope,
}) {
  assertRequired({ apiKey, database, name }, "generate-codebook");
  const normalizedDatabase = assertProjSchema(
    database,
    "database",
    "generate-codebook",
  );

  const fd = new FormData();
  fd.append("api_key", apiKey);
  fd.append("database", normalizedDatabase);
  fd.append("name", name.trim());
  fd.append(
    "sample_percentage",
    String(clampPct(samplePercentage, { min: 0 })),
  );

  if (!isBlank(model)) fd.append("model", model);
  if (!isBlank(prompt)) fd.append("prompt", prompt);
  if (!isBlank(description)) fd.append("description", description);
  if (projectId !== undefined && projectId !== null && projectId !== "") {
    fd.append("project_id", String(projectId));
  }
  if (!isBlank(contentScope)) fd.append("content_scope", contentScope);

  return fd;
}

/**
 * Build the multipart/form-data body for POST /api/apply-codebook/.
 * Mirrors `ApplyCodebookRequest`.
 */
export function buildApplyCodebookForm({
  apiKey,
  database,
  codebook,
  reportName,
  methodology,
  model,
  description,
  projectId,
  samplePercentage,
  contentScope,
}) {
  assertRequired(
    { apiKey, database, codebook, reportName },
    "apply-codebook",
  );
  const normalizedDatabase = assertProjSchema(
    database,
    "database",
    "apply-codebook",
  );

  const rawCodebook = String(codebook).trim();
  const isProjRef = rawCodebook.startsWith("proj_");
  const isNumericRef = /^\d+$/.test(rawCodebook);
  if (!isProjRef && !isNumericRef) {
    throw new MissingFieldsError(
      ["codebook (must be numeric File id or proj_<id> schema)"],
      "apply-codebook",
    );
  }

  const fd = new FormData();
  fd.append("api_key", apiKey);
  fd.append("database", normalizedDatabase);
  fd.append("codebook", rawCodebook);
  fd.append("report_name", reportName.trim());
  fd.append("sample_percentage", String(clampPct(samplePercentage)));

  if (!isBlank(methodology)) fd.append("methodology", methodology);
  if (!isBlank(model)) fd.append("model", model);
  if (!isBlank(description)) fd.append("description", description);
  if (projectId !== undefined && projectId !== null && projectId !== "") {
    fd.append("project_id", String(projectId));
  }
  if (!isBlank(contentScope)) fd.append("content_scope", contentScope);

  return fd;
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
