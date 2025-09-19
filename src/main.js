/* =========================================================
 * EccomiBook — Frontend vanilla (Vite)
 * main.js
 * ========================================================= */

import './styles.css';

const API_BASE_URL =
  (import.meta?.env?.VITE_API_BASE_URL) ||
  window.VITE_API_BASE_URL ||
  "https://eccomibook-backend.onrender.com";

// editor in DEMO finché non abilitiamo il PUT
const USE_DEMO_EDITOR = true;

/* ────────────────────────────────────────────────
   Utilità
   ──────────────────────────────────────────────── */
const $ = (sel) => document.querySelector(sel);
const setText = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };

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

  const dbg = document.createElement("div");
  dbg.className = "debug-url";
  dbg.innerHTML = `API: <a href="${API_BASE_URL}" target="_blank" rel="noreferrer">${API_BASE_URL}</a>`;
  el.appendChild(dbg);
}

/* ────────────────────────────────────────────────
   Libreria
   ──────────────────────────────────────────────── */
function showLibrary() {
  const lib = document.getElementById("library-section");
  if (lib) lib.style.display = "block";
  loadLibrary();
}

async function loadLibrary() {
  const list = document.getElementById("library-list");
  if (!list) return;

  list.innerHTML = "Caricamento…";

  try {
    const res = await fetch(`${API_BASE_URL}/books`);
    if (!res.ok) throw new Error(`Errore ${res.status}`);
    const data = await res.json();
    const books = data.items || [];

    if (books.length === 0) {
      list.className = "";
      list.innerHTML = "<em>Nessun libro ancora. Crea il tuo primo libro!</em>";
      return;
    }

    list.className = "library-grid";
    list.innerHTML = "";

    books.forEach(b => {
      const card = document.createElement("div");
      card.className = "book-card";
      card.innerHTML = `
        <div class="book-title">${b.title || "(senza titolo)"}</div>
        <div class="book-meta">Autore: ${b.author || "-"} — Lingua: ${b.language || "-"}</div>
        <div class="book-id">${b.id}</div>
        <div class="book-actions" style="margin-top:12px;">
          <button class="btn btn-secondary" data-open="${b.id}">Apri</button>
        </div>
      `;
      card.querySelector(`[data-open="${b.id}"]`).addEventListener("click", () => openBook(b.id));
      list.appendChild(card);
    });

  } catch (e) {
    list.className = "";
    list.innerHTML = `<span style="color:red">Errore di rete: ${e.message}</span>`;
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
    try { localStorage.setItem("last_book_id", data.book_id); } catch {}
    showLibrary();
  } catch (e) {
    alert("Errore di rete: " + e.message);
  }
}

/* ────────────────────────────────────────────────
   Editor capitolo (DEMO per ora)
   ──────────────────────────────────────────────── */
function openBook(bookId) {
  // mostra editor e pre-compila ID
  const sec = document.getElementById("editor-section");
  if (sec) sec.style.display = "block";

  $("#ed-book-id").value = bookId;
  $("#ed-chapter-id").value = $("#ed-chapter-id").value || "ch_0001";
  $("#ed-content").focus();

  try { localStorage.setItem("last_book_id", bookId); } catch {}

  const badge = document.getElementById("editor-mode-badge");
  if (badge) {
    badge.textContent = USE_DEMO_EDITOR ? "DEMO" : "REALE";
    badge.className = "badge " + (USE_DEMO_EDITOR ? "badge-gray" : "badge-green");
  }
}

function closeEditor() {
  const sec = document.getElementById("editor-section");
  if (sec) sec.style.display = "none";
}

async function saveChapter() {
  const bookId = $("#ed-book-id").value.trim();
  const chapterId = $("#ed-chapter-id").value.trim();
  const content = $("#ed-content").value;

  if (!bookId || !chapterId) {
    alert("Inserisci ID libro e ID capitolo.");
    return;
  }

  if (USE_DEMO_EDITOR) {
    alert(`(DEMO) Salvataggio capitolo\n\nLibro: ${bookId}\nCapitolo: ${chapterId}\n\nTesto (primi 200):\n${content.slice(0,200)}${content.length>200?"…":""}`);
    return;
  }

  // Quando abilitiamo il PUT backend, scommenta:
  // try {
  //   const resp = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`, {
  //     method: "PUT",
  //     headers: { "Content-Type": "application/json" },
  //     body: JSON.stringify({ content })
  //   });
  //   if (!resp.ok) throw new Error(`Errore ${resp.status}`);
  //   alert("✅ Capitolo salvato!");
  // } catch (e) {
  //   alert("❌ Errore: " + e.message);
  // }
}

/* ────────────────────────────────────────────────
   Hook UI
   ──────────────────────────────────────────────── */
function wireButtons() {
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", showLibrary);
  $("#btn-editor")?.addEventListener("click", () => {
    const last = localStorage.getItem("last_book_id");
    if (last) openBook(last);
    else alert("Apri prima un libro dalla libreria.");
  });

  $("#btn-ed-save")?.addEventListener("click", saveChapter);
  $("#btn-ed-close")?.addEventListener("click", closeEditor);
}

/* ────────────────────────────────────────────────
   Init
   ──────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();
  showLibrary(); // mostra la libreria all’avvio
});
