import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Served by FastAPI under /app/. The output directory is gitignored and built on deploy.
export default defineConfig({
  base: "/app/",
  plugins: [react(), tailwindcss()],
  build: {
    outDir: "../webapp/dist",
    emptyOutDir: true,
    // Keep every script external: the CSP has no 'unsafe-inline'.
    modulePreload: { polyfill: false },
    assetsInlineLimit: 0,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/app/config.json": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
  },
});
