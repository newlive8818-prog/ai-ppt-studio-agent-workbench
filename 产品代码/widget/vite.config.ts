import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";

export default defineConfig({
  root: fileURLToPath(new URL(".", import.meta.url)),
  plugins: [react()],
  build: {
    // Sidebar/Browser delivery is intentionally one self-contained HTML/IIFE resource.
    chunkSizeWarningLimit: 700,
    assetsInlineLimit: 1_000_000,
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        format: "iife",
        name: "AiPptStudioSurface",
        inlineDynamicImports: true,
        entryFileNames: "assets/workbench.js",
        assetFileNames: "assets/workbench.[ext]",
      },
    },
  },
});
