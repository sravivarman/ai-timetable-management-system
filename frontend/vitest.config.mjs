import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

export default defineConfig({
  esbuild: { jsx: "automatic" },
  test: { environment: "jsdom", setupFiles: ["./src/test/setup.ts"], globals: true, css: true },
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
});
