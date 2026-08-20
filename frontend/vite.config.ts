/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  // A GitHub Pages project site is served under /<repo>/, so both the built
  // asset URLs and the recorded API the screen fetches have to carry that
  // prefix. Set by the deploy workflow; "/" for every local run.
  base: process.env.BASE_PATH ?? "/",
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
