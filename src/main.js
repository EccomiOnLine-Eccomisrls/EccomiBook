/* =========================================================
 * EccomiBook — Frontend vanilla (Vite)
 * src/main.js
 * ========================================================= */

import './styles.css';

const API_BASE_URL =
  (import.meta?.env?.VITE_API_BASE_URL) ||
  window.VITE_API_BASE_URL ||
  "https://eccomibook-backend.onrender.com";

/* Utils */
const $ = (sel) => document.querySelector(sel);
const setText = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };

/* Ping backend */
async function pingBackend() {
  const el = document.getElementById("backend-status");
  if (!el) return;

  setText("backend-status", "Backend: verifico…");
  try {
    const r = await fetch(`${API_BASE_URL}/health`);
    setText("backend-status", r.ok ? "Backend: ✅ OK" : `Backend: errore ${r.status}`);
  } catch {
    setText("backend-status", "Backend: non raggiungibile");
  }

  // Mostra l’URL effettivo (mini debug)
  const dbg = document.createElement("div");
  dbg.className = "debug-url";
  dbg.innerHTML = `API: <a href="${API_BASE_URL}" target="_blank" rel="noreferrer">${API_BASE_URL}</a>`;
  el.appendChild(dbg);
}

/* Azioni */
async function createBookSimple() {
  const title = prompt("Titolo del libro:", "Manuale EccomiBook");
  if (!title) return;

  try {
    const res = await fetch(`${API_BASE_URL}/books/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        author: "EccomiBook",
        language: "it",
        chapters: []
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`Errore (${res.status}): ${err.detail || JSON.stringify(err)}`);
      return;
    }

    const data = await res.json();
    alert(`✅ Libro creato!\nID: ${data.book_id}\nTitolo: ${data.title}`);
    try { localStorage.setItem("last_book_id", data.book_id); } catch {}
  } catch (e) {
    alert("Errore di rete: " + e.message);
  }
}

function goLibrary() { alert("📖 Libreria — in arrivo"); }
function goEditor()  { alert("✏️ Editor — in arrivo");  }

/* Hook UI */
function wireButtons() {
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", goLibrary);
  $("#btn-editor")?.addEventListener("click", goEditor);
}

/* Init */
document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();
});
