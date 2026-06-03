import { defineConfig } from "vite";

// Optional richer SPA build. Output goes to ./dist; point the backend's static
// mount at ./dist if you adopt this path. Relative base keeps Ingress working.
export default defineConfig({
  base: "./",
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      // During `npm run dev`, proxy API calls to a locally running gateway.
      "/api": "http://localhost:8099",
      "/health": "http://localhost:8099",
    },
  },
});
