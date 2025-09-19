/* =========================================================
 * EccomiBook — Frontend vanilla (Vite)
 * main.js (completo)
 * ========================================================= */

import './styles.css';

const API_BASE_URL =
  (import.meta?.env?.VITE_API_BASE_URL) ||
  window.VITE_API_BASE_URL ||
  "https://eccomibook-backend.onrender.com";

/* ───────────── Util ───────────── */
const $ = (sel) => document.querySelector(sel);
const setText = (id, txt) => { const el = document.getElementById(id); if (el) el.textContent = txt; };

/* ──────────── Backend badge ──────────── */
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

  // mini debug con URL API
  const dbg = document.createElement("div");
  dbg.className = "debug-url";
  dbg.innerHTML = `API: <a href="${API_BASE_URL}" target="_blank">${API_BASE_URL}</a>`;
  el.appendChild(dbg);
}

/* ─────────── Azioni ─────────── */
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
    await loadLibrary();        // aggiorna subito la libreria
    showLibrarySection();       // e assicurati che sia visibile
  } catch (e) {
    alert("Errore di rete: " + e.message);
  }
}

function showLibrarySection() {
  const lib = document.getElementById("library-section");
  if (lib) lib.style.display = "block";
}

async function loadLibrary() {
  const box = document.getElementById("library-list");
  if (!box) return;

  box.innerHTML = "Carico libreria…";
  try {
    const res = await fetch(`${API_BASE_URL}/books`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      box.innerHTML = `<span style="color:#ff6b6b;">Errore (${res.status}): ${err.detail || 'Not Found'}</span>`;
      return;
    }
    const items = await res.json();

    if (!items || items.length === 0) {
      box.innerHTML = `<div class="card">Nessun libro ancora. Crea il tuo primo libro con “+ Crea libro”.</div>`;
      return;
    }

    // Render semplice: lista dei libri (titolo + id)
    const ul = document.createElement("ul");
    ul.style.listStyle = "none";
    ul.style.padding = "0";
    ul.style.margin = "0";

    items.forEach(b => {
      const li = document.createElement("li");
      li.className = "card";
      li.style.margin = "10px 0";
      li.innerHTML = `
        <div class="card-head">
          <strong>${b.title || '(senza titolo)'}</strong>
          <span class="badge badge-gray">${b.id}</span>
        </div>
        <div style="opacity:.8">${b.author ? `Autore: ${b.author} — ` : ""}Lingua: ${b.language || 'it'}</div>
      `;
      ul.appendChild(li);
    });

    box.innerHTML = "";
    box.appendChild(ul);
  } catch (e) {
    box.innerHTML = `<span style="color:#ff6b6b;">Errore di rete: ${e.message}</span>`;
  }
}

/* ─────────── UI Hooks ─────────── */
function wireButtons() {
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", () => { showLibrarySection(); loadLibrary(); });
  $("#btn-editor")?.addEventListener("click", () => alert("Editor capitolo — in arrivo"));
}

/* ─────────── Init ─────────── */
document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();
  // opzionale: carica la libreria all'avvio
  // showLibrarySection(); await loadLibrary();
});
