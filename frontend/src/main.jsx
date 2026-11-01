
import React from "react";
import { createRoot } from "react-dom/client";

import AuthGate from "./AuthGate.jsx";
import "./style.css";
import "./AuthGate.css";

const root = document.getElementById("root");

createRoot(root).render(
  <AuthGate />
);
