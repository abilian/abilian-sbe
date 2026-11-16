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
        // Only documents/view_pdf.html loads these two.
        pdfviewer: "./src/pdfviewer.js",
        "pdfviewer-styles": "./src/pdfviewer-styles.css",
      },
      output: {
        entryFileNames: "[name].js",
        // Stable names: the templates load them by name (vite_asset()).
        assetFileNames: "[name][extname]",
      },
    },
    outDir: "dist",
    assetsDir: "",
    manifest: false,
  },
});
