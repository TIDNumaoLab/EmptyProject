/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    // 呼び出し回数などの記録を試験ごとに消す
    clearMocks: true,
    css: { modules: { classNameStrategy: "non-scoped" } },
  },
});
