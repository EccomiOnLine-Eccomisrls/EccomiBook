/* =========================================================
 * EccomiBook — Frontend vanilla (Vite)
 * main.js
 * ========================================================= */

import './styles.css';
const API_BASE_URL =
  (import.meta?.env?.VITE_API_BASE_URL) ||
  window.VITE_API_BASE_URL ||
  "https://eccomibook-backend.onrender.com";

/* ────────────────────────────────────────────────
   Utilità
   ──────────────────────────────────────────────── */
function $(sel) { return document.querySelector(sel); }
function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

/* ────────────────────────────────────────────────
   Ping backend
   ──────────────────────────────────────────────── */
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

  // debug URL
  const dbg = document.createElement("div");
  dbg.className = "debug-url";
  dbg.innerHTML = `API: <a href="${API_BASE_URL}" target="_blank">${API_BASE_URL}</a>`;
  el.appendChild(dbg);
}

/* ────────────────────────────────────────────────
   Azioni
   ──────────────────────────────────────────────── */
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
    await loadLibrary(); // aggiorna subito la libreria
  } catch (e) {
    alert("Errore di rete: " + e.message);
  }
}

async function loadLibrary() {
  const list = document.getElementById("library-list");
  if (!list) return;

  list.innerHTML = "Caricamento…";

  try {
    const res = await fetch(`${API_BASE_URL}/books`);
    if (!res.ok) throw new Error(`Errore ${res.status}`);

    const data = await res.json();
    const books = data.items || []; // FIX QUI ✅

    if (books.length === 0) {
      list.innerHTML = "<em>Nessun libro ancora. Crea il tuo primo libro!</em>";
      return;
    }

    list.innerHTML = "";
    books.forEach(b => {
      const o = document.createElement("div");
      o.className = "card";
      o.style.margin = "10px 0";
      o.innerHTML = `
        <strong>${b.title || "(senza titolo)"}</strong><br>
        Autore: ${b.author || "-"} — Lingua: ${b.language || "-"}<br>
        <small>${b.id}</small>
      `;
      list.appendChild(o);
    });

  } catch (e) {
    list.innerHTML = `<span style="color:red">Errore di rete: ${e.message}</span>`;
  }
}

function goLibrary() {
  const lib = document.getElementById("library-section");
  if (lib) lib.style.display = "block";
  loadLibrary();
}

function goEditor() {
  alert("✏️ Editor capitolo — funzione in arrivo");
}

/* ────────────────────────────────────────────────
   Hook UI
   ──────────────────────────────────────────────── */
function wireButtons() {
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", goLibrary);
  $("#btn-editor")?.addEventListener("click", goEditor);
}

/* ────────────────────────────────────────────────
   Init
   ──────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();
});
