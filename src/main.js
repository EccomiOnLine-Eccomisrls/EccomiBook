// Importa gli stili
import "./styles.css";

// Backend API
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// Debug rapido in alto
const backendStatus = document.getElementById("backend-status");
fetch(`${API_BASE_URL}/health`)
  .then((res) => res.json())
  .then((data) => {
    backendStatus.textContent = "Backend: OK";
    const debugLine = document.createElement("div");
    debugLine.style.fontSize = "10px";
    debugLine.style.opacity = "0.6";
    debugLine.textContent = `API: ${API_BASE_URL}`;
    backendStatus.appendChild(debugLine);
  })
  .catch(() => {
    backendStatus.textContent = "Backend: non raggiungibile";
  });

// Pulsanti demo
document.getElementById("btn-new-book").onclick = () => {
  alert("Nuovo libro in arrivo!");
};
document.getElementById("btn-library").onclick = () => {
  alert("Apro la libreria...");
};
document.getElementById("btn-edit-chapter").onclick = () => {
  alert("Editor capitolo in arrivo!");
};
