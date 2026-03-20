import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@chatscope/chat-ui-kit-react/dist/styles/default/styles.min.css":
        path.resolve(__dirname, "./src/__mocks__/empty.css"),
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
    css: true,
    env: {
      VITE_API_BASE: "",
    },
  },
});
