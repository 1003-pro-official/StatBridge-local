import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import AccountGate from "./AccountGate";
import "./styles.css";
import "./professional.css";
import "./controls.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AccountGate><App /></AccountGate>
  </StrictMode>,
);
