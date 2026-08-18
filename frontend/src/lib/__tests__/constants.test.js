import { describe, it, expect } from "vitest";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { AI_MODELS } from "../constants";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "../../../..");

describe("openrouter_models.json catalog", () => {
  it("re-exports the JSON import as AI_MODELS", () => {
    expect(Array.isArray(AI_MODELS)).toBe(true);
    expect(AI_MODELS.length).toBeGreaterThan(0);
  });

  it("frontend/constants and backend/constants copies stay byte-identical", () => {
    // The backend (backend/app/ai_models.py) and frontend both ship their
    // own copy of this file. There's no build step that keeps them in
    // sync, so a drift here means the two catalogs silently disagree
    // about available models/pricing.
    const frontendPath = path.join(repoRoot, "frontend", "constants", "openrouter_models.json");
    const backendPath = path.join(repoRoot, "backend", "constants", "openrouter_models.json");
    const frontendRaw = fs.readFileSync(frontendPath, "utf-8");
    const backendRaw = fs.readFileSync(backendPath, "utf-8");
    expect(frontendRaw).toBe(backendRaw);
  });
});
