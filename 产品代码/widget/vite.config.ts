import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  root: fileURLToPath(new URL(".", import.meta.url)),
  plugins: [react()],
  build: {
    outDir: "dist-raw",
    emptyOutDir: true,
    assetsInlineLimit: 1_000_000,
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        format: "iife",
        name: "AiPptStudioWidget",
        inlineDynamicImports: true,
        entryFileNames: "assets/workbench.js",
        assetFileNames: "assets/workbench.[ext]",
      },
    },
  },
});
