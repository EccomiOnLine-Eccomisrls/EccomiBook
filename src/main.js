/* =========================================================
 * EccomiBook — Frontend vanilla (Vite)
 * main.js (unificato)
 * ========================================================= */

import './styles.css';

const API_BASE_URL =
  (import.meta?.env?.VITE_API_BASE_URL) ||
  window.VITE_API_BASE_URL ||
  "https://eccomibook-backend.onrender.com";

/* ───────────── Util ───────────── */
const $ = (sel) => document.querySelector(sel);
const setText = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };

/* ───────── Ping backend ───────── */
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
  const dbg = document.createElement("div");
  dbg.className = "debug-url";
  dbg.innerHTML = `API: <a href="${API_BASE_URL}" target="_blank" rel="noreferrer">${API_BASE_URL}</a>`;
  el.appendChild(dbg);
}

/* ───────── Azioni ───────── */
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

/* ───────── Libreria ───────── */
async function loadLibrary() {
  const container = document.getElementById("library-list");
  if (!container) return;

  container.innerHTML = "<p>📚 Caricamento libreria...</p>";

  try {
    const res = await fetch(`${API_BASE_URL}/books`, {
      method: "GET",
      headers: { "Content-Type": "application/json" }
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      container.innerHTML = `<p style="color:#ff6b6b">Errore (${res.status}): ${err.detail || "Impossibile caricare i libri"}</p>`;
      return;
    }

    const data = await res.json(); // atteso oggetto { id: {...}, ... } oppure array
    const books = Array.isArray(data) ? data : Object.values(data || {});
    if (!books.length) {
      container.innerHTML = "<p>📭 Nessun libro trovato.</p>";
      return;
    }

    container.innerHTML = "";
    books.forEach(book => {
      const div = document.createElement("div");
      div.className = "card";
      div.innerHTML = `
        <div class="card-head"><strong>${book.title}</strong></div>
        <p><small>ID: ${book.id}</small></p>
        <p>Autore: ${book.author || "-"}</p>
      `;
      container.appendChild(div);
    });
  } catch (e) {
    container.innerHTML = `<p style="color:#ff6b6b">❌ Errore di rete: ${e.message}</p>`;
  }
}

function goLibrary() {
  const lib = document.getElementById("library-section");
  if (lib) lib.style.display = "block";
  loadLibrary();
}

/* (placeholder) Editor */
function goEditor() {
  alert("✏️ Editor capitolo — in arrivo");
}

/* ───────── Hook UI ───────── */
function wireButtons() {
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", goLibrary);
  $("#btn-editor")?.addEventListener("click", goEditor);
}

/* ───────── Init ───────── */
document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();
});
