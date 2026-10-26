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
const requireLoopbackDevelopmentUrl = (value, field) => {
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    throw new Error(`${field} must be an absolute loopback URL for the Vite development server.`);
  }
  if (!["localhost", "127.0.0.1", "[::1]"].includes(parsed.hostname)) {
    throw new Error(`${field} must remain loopback-only for the Vite development server.`);
  }
  return value;
};

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, import.meta.dirname, "");
  const devApiTarget = env.VITE_DEV_PROXY_TARGET || "http://127.0.0.1:8000";
  const devProxyRequestOrigin = env.VITE_DEV_PROXY_REQUEST_ORIGIN?.replace(/\/+$/, "");
  if (command === "serve") {
    requireLoopbackDevelopmentUrl(devApiTarget, "VITE_DEV_PROXY_TARGET");
    if (devProxyRequestOrigin) {
      requireLoopbackDevelopmentUrl(devProxyRequestOrigin, "VITE_DEV_PROXY_REQUEST_ORIGIN");
    }
  }
  const devProxyOptions = {
    target: devApiTarget,
    changeOrigin: true,
    ...(devProxyRequestOrigin
      ? {
          headers: {
            Origin: devProxyRequestOrigin,
            Referer: `${devProxyRequestOrigin}/`,
          },
        }
      : {}),
  };

  return {
    plugins: [react()],
    test: {
      // Components under test expect every translation namespace, as the portal has.
      setupFiles: ["./src/i18n/allTranslations.js"],
    },
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
          ...devProxyOptions,
        },
        "/api": {
          ...devProxyOptions,
          rewrite: (path) => path.replace(/^\/api/, ""),
        },

        "/avatar_uploads": {
          ...devProxyOptions,
        },
      },
    },
  };
});
