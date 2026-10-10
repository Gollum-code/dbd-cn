import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import fs from "node:fs";
import path from "node:path";

// Serve the crawler's icon folder at /icons/* during `vite dev`, so the UI
// renders icons in the browser too (packaged builds read them from the
// Tauri resource dir instead — see src/api.js `iconUrl`).
const ICON_ROOT = path.resolve(__dirname, "..", "data", "icons");

function iconsPlugin() {
  return {
    name: "dbd-icons",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = req.url || "";
        if (!url.startsWith("/icons/")) return next();
        const rel = decodeURIComponent(url.slice("/icons/".length).split("?")[0]);
        const target = path.join(ICON_ROOT, rel);
        // keep the resolved path inside ICON_ROOT
        if (!target.startsWith(ICON_ROOT) || !fs.existsSync(target)) {
          res.statusCode = 404;
          return res.end("not found");
        }
        const ext = path.extname(target).toLowerCase();
        const types = { ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp" };
        res.setHeader("Content-Type", types[ext] || "application/octet-stream");
        res.setHeader("Cache-Control", "public, max-age=86400");
        fs.createReadStream(target).pipe(res);
      });
    },
  };
}

export default defineConfig({
  plugins: [vue(), iconsPlugin()],
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    watch: { ignored: ["**/src-tauri/**"] },
  },
  build: {
    outDir: "dist",
    target: "chrome110",
    minify: "esbuild",
  },
});