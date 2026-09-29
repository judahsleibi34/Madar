import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// These small Lucide modules are shared by the published-site renderer and its
// chrome. Keep this bounded: private/editor-only icons stay in their own routes.
const publicIconModules = new Set([
  "arrow-right", "bell", "calendar-days", "check", "chevron-down",
  "chevron-right", "download", "earth", "external-link", "file-text",
  "gift", "mail", "map-pin", "palette", "phone", "rotate-ccw",
  "shopping-bag", "sparkles", "sun", "user-round", "users-round", "x",
]);

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, import.meta.dirname, "");
  const devApiTarget = env.VITE_DEV_PROXY_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    build: {
      manifest: true,
      // Safari 14 cannot parse some modern syntax shipped by dependencies such as Three.js.
      // Transpile the complete production bundle, including vendor chunks, to that browser level.
      target: "safari14",
      rolldownOptions: {
        output: {
          manualChunks(id) {
            const icon = id.match(/[/\\]lucide-react[/\\]dist[/\\]esm[/\\]icons[/\\]([^/\\]+)\.mjs$/);
            if (icon && publicIconModules.has(icon[1])) return "public-icons";
            if (id.includes("node_modules/three") || id.includes("node_modules\\three")) {
              return "vendor-three";
            }
          },
        },
      },
    },
    server: {
      proxy: {
        "/uploads": {
          target: devApiTarget,
          changeOrigin: true,
        },
        "/api": {
          target: devApiTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },

        "/avatar_uploads": {
          target: devApiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
