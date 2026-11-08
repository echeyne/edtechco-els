import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { applyLegacyRedirect } from "./router";
import "./index.css";

// Old hash links (#privacy, #terms, #contact) become real paths before the
// first render, so they never flash the home page.
applyLegacyRedirect();

const root = createRoot(document.getElementById("root")!);
root.render(
  <StrictMode>
    <App />
  </StrictMode>,
);
