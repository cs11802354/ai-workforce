import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// The trust-panel page lives outside src/ so that multi_model_trust/ stays a
// self-contained directory that can be handed over on its own. The alias is
// what lets the app import it without a copy.
const trustUi = fileURLToPath(new URL("../multi_model_trust/ui", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@trust": trustUi } },
  server: {
    port: 5173,
    fs: { allow: [fileURLToPath(new URL("..", import.meta.url))] },
  },
});
