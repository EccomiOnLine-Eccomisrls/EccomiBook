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
const $ = (sel) => document.querySelector(sel);
const setText = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };

/* ────────────────────────────────────────────────
   Backend status
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

  // mini-debug URL
  const dbg = document.createElement("div");
  dbg.className = "debug-url";
  dbg.innerHTML = `API: <a href="${API_BASE_URL}" target="_blank" rel="noreferrer">${API_BASE_URL}</a>`;
  el.appendChild(dbg);
}

/* ────────────────────────────────────────────────
   Libreria
   ──────────────────────────────────────────────── */
/** Normalizza la risposta di /books in un array di libri {id,title,author,language,...} */
function normalizeBooksPayload(payload) {
  // 1) array diretto
  if (Array.isArray(payload)) return payload;

  // 2) { items: [...] , count: n }
  if (payload && Array.isArray(payload.items)) return payload.items;

  // 3) { books: [...] }  oppure  { books: { id: {...} } }
  if (payload && payload.books) {
    const b = payload.books;
    if (Array.isArray(b)) return b;
    if (typeof b === "object") {
      return Object.keys(b).map(id => ({ id, ...(b[id] || {}) }));
    }
  }

  // 4) dict per id
  if (payload && typeof payload === "object") {
    return Object.keys(payload).map(id => ({ id, ...(payload[id] || {}) }));
  }

  return [];
}

async function fetchBooks() {
  const res = await fetch(`${API_BASE_URL}/books`);
  if (!res.ok) throw new Error(`Errore (${res.status})`);
  const data = await res.json();
  return normalizeBooksPayload(data);
}

function renderLibrary(books = []) {
  const container = document.getElementById("library-list");
  if (!container) return;

  container.innerHTML = "";

  if (!books.length) {
    container.innerHTML = `<div class="card" style="opacity:.8">Nessun libro ancora. Crea il tuo primo libro con “Crea libro”.</div>`;
    return;
  }

  books.forEach((b) => {
    const id = b.id || b.book_id || "";
    const title = b.title || "(senza titolo)";
    const author = b.author || "—";
    const language = b.language || "it";

    const card = document.createElement("div");
    card.className = "card";
    card.style.margin = "10px 0";
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;">
        <div>
          <div style="font-weight:600">${title}</div>
          <div style="font-size:13px;opacity:.8">Autore: ${author} — Lingua: ${language}</div>
        </div>
        <code style="opacity:.7">${id}</code>
      </div>
      <div class="row-right" style="margin-top:10px">
        <button class="btn btn-secondary" data-open-id="${id}">Apri</button>
        <button class="btn btn-ghost" data-edit-id="${id}">Modifica</button>
        <button class="btn btn-ghost" data-del-id="${id}">Elimina</button>
      </div>
    `;
    container.appendChild(card);
  });

  // wire “Apri”
  container.querySelectorAll("[data-open-id]").forEach(btn => {
    btn.addEventListener("click", () => openBook(btn.getAttribute("data-open-id")));
  });
}

/* mostra la sezione libreria */
async function showLibrary() {
  $("#library-section").style.display = "block";
  try {
    const books = await fetchBooks();
    renderLibrary(books);
  } catch (e) {
    document.getElementById("library-list").innerHTML =
      `<div class="card" style="border-color:#5a2a2a;color:#f2b5b5">Errore di rete: ${e.message}</div>`;
  }
}

/* ────────────────────────────────────────────────
   Crea libro
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
    const newId = data.book_id || data.id;
    alert(`✅ Libro creato!\nID: ${newId}\nTitolo: ${data.title || title}`);
    try { localStorage.setItem("last_book_id", newId); } catch {}

    // aggiorna libreria a vista
    showLibrary();
  } catch (e) {
    alert("Errore di rete: " + e.message);
  }
}

/* ────────────────────────────────────────────────
   Editor capitolo (placeholder)
   ──────────────────────────────────────────────── */
function openBook(bookId) {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "block";
  const book = $("#bookIdInput");
  const ch = $("#chapterIdInput");
  const tx = $("#chapterText");
  if (book) book.value = bookId || "";
  if (ch && !ch.value) ch.value = "ch_0001";
  if (tx && !tx.value) tx.value = "";
  try { localStorage.setItem("last_book_id", bookId); } catch {}
}

function closeEditor() {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "none";
}

async function saveChapter() {
  alert("Salvataggio capitolo: endpoint PUT verrà abilitato nella prossima iterazione.");
}

/* ────────────────────────────────────────────────
   Hook UI
   ──────────────────────────────────────────────── */
function wireButtons() {
  // Topbar
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", showLibrary);
  $("#btn-editor")?.addEventListener("click", () => {
    const last = localStorage.getItem("last_book_id");
    if (last) openBook(last);
    else alert("Apri prima un libro dalla libreria.");
  });

  // Azioni rapide (card) – ID diversi per evitare conflitti
  $("#btn-create-book-2")?.addEventListener("click", createBookSimple);
  $("#btn-library-2")?.addEventListener("click", showLibrary);
  $("#btn-editor-2")?.addEventListener("click", () => {
    const last = localStorage.getItem("last_book_id");
    if (last) openBook(last);
    else alert("Apri prima un libro dalla libreria.");
  });

  // Editor
  $("#btn-ed-save")?.addEventListener("click", saveChapter);
  $("#btn-ed-close")?.addEventListener("click", closeEditor);
}

/* ────────────────────────────────────────────────
   Init
   ──────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();

  // badge modalità (placeholder)
  const modeBadge = document.getElementById("editor-mode-badge");
  if (modeBadge) {
    modeBadge.textContent = "DEMO";
    modeBadge.className = "badge badge-gray";
  }

  // mostra la libreria all’avvio (opzionale)
  await showLibrary();
});
