import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const contentReviewCss = readFileSync(
  fileURLToPath(new URL("./widget/src/styles.css", import.meta.url)),
  "utf8",
);

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
