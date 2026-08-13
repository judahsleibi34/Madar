import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, import.meta.dirname, "");
  const devApiTarget = env.VITE_DEV_PROXY_TARGET || "http://127.0.0.1:8002";

  return {
    plugins: [react()],
    build: {
      // Safari 14 cannot parse some modern syntax shipped by dependencies such as Three.js.
      // Transpile the complete production bundle, including vendor chunks, to that browser level.
      target: "safari14",
      rolldownOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("node_modules/three") || id.includes("node_modules\\three")) {
              return "vendor-three";
            }
          },
        },
      },
    },
    server: {
      proxy: {
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