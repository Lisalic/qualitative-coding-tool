/**
 * "Still needed: a name, a project." for a disabled setup button, from
 * `[label, isMissing]` pairs; empty when nothing is missing.
 */
export function missingHint(fields) {
  const missing = fields.filter(([, isMissing]) => isMissing).map(([label]) => label);
  return missing.length ? `Still needed: ${missing.join(", ")}.` : "";
}
