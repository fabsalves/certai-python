import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./styles/tokens.css";
import "./styles/shell.css";
import "./styles/track-path.css";
import "./styles/track-structure.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
