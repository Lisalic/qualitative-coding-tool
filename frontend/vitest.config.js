import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Standalone config rather than reusing vite.config.js: that file exports a
// function (it needs `loadEnv`/`mode` for the dev-server API proxy), and
// none of that dev-only wiring is relevant to tests.
export default defineConfig({
  plugins: [react()],
  test: {
    // Most of the test suite is pure logic (no DOM) and runs fine -- and
    // faster -- under plain node. Only files that touch `window`/
    // `localStorage`/`fetch` opt in to jsdom via a per-file
    // `// @vitest-environment jsdom` docblock (see src/api.test.js).
    environment: "node",
    globals: false,
    coverage: {
      provider: "v8",
      reporter: ["text", "html"],
      include: ["src/lib/**", "src/api.js"],
    },
  },
});
