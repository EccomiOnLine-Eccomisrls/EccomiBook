// src/main.js
import './styles.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "undefined";

// Funzione che controlla lo stato del backend
async function checkBackend() {
  const statusEl = document.getElementById('backend-status');
  try {
    const res = await fetch(`${API_BASE_URL}/health`);
    if (res.ok) {
      statusEl.textContent = "Backend: raggiungibile ✅";
      statusEl.style.color = "lightgreen";
    } else {
      statusEl.textContent = "Backend: non raggiungibile ❌";
      statusEl.style.color = "red";
    }
  } catch (e) {
    statusEl.textContent = "Backend: non raggiungibile ❌";
    statusEl.style.color = "red";
  }

  // Mostra l'URL effettivo (mini debug)
  const debugLine = document.createElement('div');
  debugLine.style.fontSize = '10px';
  debugLine.style.opacity = '0.6';
  debugLine.textContent = `API: ${API_BASE_URL}`;
  statusEl.appendChild(debugLine);
}

checkBackend();
