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
  debugLine.style.marginTop = '4px';
  debugLine.textContent = `API: ${API_BASE_URL}`;
  statusEl.appendChild(debugLine);
}

// UI: Bottoni principali
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("btn-crea-libro").addEventListener("click", () => {
    alert("📖 Funzione Crea Libro (da collegare al backend)");
  });

  document.getElementById("btn-libreria").addEventListener("click", () => {
    alert("📚 Funzione Libreria (da collegare al backend)");
  });

  document.getElementById("btn-modifica-capitolo").addEventListener("click", () => {
    alert("✍️ Funzione Modifica Capitolo (da collegare al backend)");
  });

  checkBackend();
});
