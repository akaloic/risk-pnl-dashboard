/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    // The pure-logic suites need no DOM and run faster without one, so the
    // browser environment is opted into per file with a `@vitest-environment`
    // comment rather than imposed on everything.
    environment: "node",
    globals: false,
    restoreMocks: true,
    setupFiles: ["src/test/setup.ts"],
  },
});
