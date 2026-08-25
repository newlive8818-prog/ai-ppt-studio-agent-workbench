import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const contentReviewCss = [
  "./widget/src/styles.css",
  "./widget/src/styles/content-review.css",
  "./widget/src/styles/evidence.css",
].map((relativePath) => readFileSync(
  fileURLToPath(new URL(relativePath, import.meta.url)),
  "utf8",
)).join("\n");

export default defineConfig({
  plugins: [react()],
  define: {
    __AI_PPT_CONTENT_REVIEW_CSS__: JSON.stringify(contentReviewCss),
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./widget/src/test-setup.ts"],
    include: ["widget/src/**/*.test.tsx"],
    server: {
      deps: {
        external: [/@testing-library\/jest-dom/],
      },
    },
  },
});
