/* =========================================================
 * EccomiBook — Frontend vanilla (Vite)
 * src/main.js
 * ========================================================= */

import './styles.css';

const API_BASE_URL =
  (import.meta?.env?.VITE_API_BASE_URL) ||
  window.VITE_API_BASE_URL ||
  "https://eccomibook-backend.onrender.com";

/* ────────────────────────────────────────────────
   Helpers
   ──────────────────────────────────────────────── */
const $ = (sel) => document.querySelector(sel);
const el = (tag, cls) => { const x = document.createElement(tag); if (cls) x.className = cls; return x; };
const setText = (id, text) => { const x = document.getElementById(id); if (x) x.textContent = text; };

/* ────────────────────────────────────────────────
   Ping backend (badge)
   ──────────────────────────────────────────────── */
async function pingBackend() {
  const badge = $("#backend-status");
  if (!badge) return;
  setText("backend-status", "Backend: verifico…");

  try {
    const r = await fetch(`${API_BASE_URL}/health`);
    setText("backend-status", r.ok ? "Backend: ✅ OK" : `Backend: errore ${r.status}`);
  } catch {
    setText("backend-status", "Backend: non raggiungibile");
  }

  // mini-debug URL
  const dbg = el("div", "debug-url");
  dbg.innerHTML = `API: <a href="${API_BASE_URL}" target="_blank" rel="noreferrer">${API_BASE_URL}</a>`;
  badge.appendChild(dbg);
}

/* ────────────────────────────────────────────────
   Libreria
   ──────────────────────────────────────────────── */
async function fetchBooks() {
  try {
    const r = await fetch(`${API_BASE_URL}/books`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    return { error: e.message };
  }
}

function renderLibraryList(listEl, books) {
  listEl.innerHTML = "";
  if (!Array.isArray(books) || books.length === 0) {
    const empty = el("div"); empty.style.opacity = ".75";
    empty.textContent = "Nessun libro ancora. Crea il tuo primo libro con “Crea libro”.";
    listEl.appendChild(empty);
    return;
  }

  books.forEach((b) => {
    const card = el("div", "card"); card.style.margin = "10px 0";
    card.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px">
        <div>
          <div style="font-weight:600">${b.title || "(senza titolo)"}</div>
          <div style="font-size:13px;opacity:.8">Autore: ${b.author || "—"} — Lingua: ${b.language || "it"}</div>
          <div><span class="badge" style="margin-top:6px">${b.id}</span></div>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn btn-secondary" data-action="open" data-id="${b.id}">Apri</button>
          <button class="btn btn-ghost" data-action="edit" data-id="${b.id}">Modifica</button>
          <button class="btn btn-ghost" data-action="delete" data-id="${b.id}">Elimina</button>
        </div>
      </div>
    `;
    listEl.appendChild(card);
  });

  // wire azioni
  listEl.querySelectorAll("button[data-action='open']").forEach(btn => {
    btn.addEventListener("click", () => openEditorForBook(btn.dataset.id));
  });
}

/* Toggle libreria */
function toggleLibrary(show) {
  const sec = $("#library-section");
  if (!sec) return;
  sec.style.display = show ? "block" : "none";
  const toggleBtn = $("#btn-library-toggle");
  if (toggleBtn) toggleBtn.textContent = show ? "Chiudi libreria" : "Apri libreria";
}

async function openLibraryAndReload() {
  toggleLibrary(true);
  const list = $("#library-list");
  list.innerHTML = "Carico…";
  const data = await fetchBooks();
  if (data?.error) {
    list.innerHTML = `<div style="color:#f77">Errore: ${data.error}</div>`;
  } else {
    renderLibraryList(list, data);
  }
}

/* ────────────────────────────────────────────────
   Crea libro (modale semplice via prompt)
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
    await openLibraryAndReload();
    openEditorForBook(data.book_id);     // apri editor direttamente
  } catch (e) {
    alert("Errore di rete: " + e.message);
  }
}

/* ────────────────────────────────────────────────
   Editor capitolo (REALE)
   ──────────────────────────────────────────────── */
function openEditor() {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "block";
}

function closeEditor() {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "none";
}

function openEditorForBook(bookId) {
  openEditor();
  const b = $("#bookIdInput");
  const ch = $("#chapterIdInput");
  const tx = $("#chapterText");
  if (b) b.value = bookId || (localStorage.getItem("last_book_id") || "");
  if (ch && !ch.value) ch.value = "ch_0001";
  if (tx && !tx.value) tx.value = "";
}

async function saveChapter() {
  const bookId = $("#bookIdInput")?.value?.trim();
  const chId = $("#chapterIdInput")?.value?.trim();
  const text = $("#chapterText")?.value ?? "";

  if (!bookId || !chId) {
    alert("Inserisci ID libro e ID capitolo.");
    return;
  }

  try {
    const resp = await fetch(
      `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chId)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: text, title: null }),
      }
    );

    if (!resp.ok) {
      let msg = `Errore ${resp.status}`;
      try {
        const j = await resp.json();
        if (j?.detail) msg = j.detail;
      } catch {}
      throw new Error(msg);
    }

    alert("✅ Capitolo salvato!");
  } catch (err) {
    alert("❌ Errore: " + (err?.message || String(err)));
  }
}

/* ────────────────────────────────────────────────
   Hook UI
   ──────────────────────────────────────────────── */
function wireButtons() {
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library-toggle")?.addEventListener("click", () => {
    const sec = $("#library-section");
    toggleLibrary(sec?.style.display !== "block");
    if (sec?.style.display === "block") openLibraryAndReload();
  });
  $("#btn-editor")?.addEventListener("click", () => openEditorForBook(localStorage.getItem("last_book_id")||""));

  $("#btn-ed-save")?.addEventListener("click", saveChapter);
  $("#btn-ed-close")?.addEventListener("click", closeEditor);

  // “Azioni rapide”
  $("#btn-quick-new")?.addEventListener("click", createBookSimple);
  $("#btn-quick-lib")?.addEventListener("click", () => {
    toggleLibrary(true); openLibraryAndReload();
  });
  $("#btn-quick-editor")?.addEventListener("click", () => openEditorForBook(localStorage.getItem("last_book_id")||""));
}

/* ────────────────────────────────────────────────
   Init
   ──────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();
  // Apri libreria all’avvio (opzionale: metti false se la vuoi chiusa di default)
  toggleLibrary(true);
  openLibraryAndReload();
});

/* Esporta in window se servisse inline */
window.openEditorForBook = openEditorForBook;
