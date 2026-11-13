import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [tailwindcss()],
  // Pinned, and strict on purpose: without strictPort Vite silently moves to
  // the next free port when this one is taken, while Flask keeps emitting
  // VITE_DEV_SERVER -- so every asset tag points at whatever else is running
  // there. Keep in sync with VITE_DEV_SERVER in abilian/setup/extensions.py.
  server: {
    port: 5180,
    strictPort: true,
  },
  build: {
    rollupOptions: {
      input: {
        main: "./src/main.js",
        styles: "./src/styles.css",
        // Only admin/dashboard.html loads this one.
        charts: "./src/charts.js",
        // Only the rich text widget loads this one.
        editor: "./src/editor.js",
      },
      output: {
        entryFileNames: "[name].js",
        assetFileNames: "[name].css",
      },
    },
    outDir: "dist",
    assetsDir: "",
    manifest: false,
  },
});
