/* =========================================================
 * EccomiBook — Frontend (Vite, vanilla)
 * main.js — COMPLETO
 * ========================================================= */

import "./styles.css";

/* ───────────────────────────────────────────────
   Config
   ─────────────────────────────────────────────── */
const API_BASE_URL =
  (import.meta?.env?.VITE_API_BASE_URL) ||
  window.VITE_API_BASE_URL ||
  "https://eccomibook-backend.onrender.com";

/* ───────────────────────────────────────────────
   Util
   ─────────────────────────────────────────────── */
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}
function toast(msg) { alert(msg); }

function rememberLastBook(id) {
  try { localStorage.setItem("last_book_id", id || ""); } catch {}
}
function loadLastBook() {
  try { return localStorage.getItem("last_book_id") || ""; } catch { return ""; }
}

function escapeHtml(s) { return String(s ?? "").replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }
function escapeAttr(s) { return escapeHtml(s).replace(/"/g, "&quot;"); }

/* ───────────────────────────────────────────────
   Stato UI
   ─────────────────────────────────────────────── */
const uiState = { libraryVisible: false };

/* ───────────────────────────────────────────────
   Backend ping + badge
   ─────────────────────────────────────────────── */
async function pingBackend() {
  const el = document.getElementById("backend-status");
  if (!el) return;

  setText("backend-status", "Backend: verifico…");
  try {
    const r = await fetch(`${API_BASE_URL}/health`, { method: "GET" });
    setText("backend-status", r.ok ? "Backend: ✅ OK" : `Backend: errore ${r.status}`);
  } catch {
    setText("backend-status", "Backend: non raggiungibile");
  }

  const dbg = document.createElement("div");
  dbg.className = "debug-url";
  dbg.innerHTML = `API: <a href="${API_BASE_URL}" target="_blank" rel="noreferrer">${API_BASE_URL}</a>`;
  el.appendChild(dbg);
}

/* ───────────────────────────────────────────────
   Libreria: API + render
   ─────────────────────────────────────────────── */
async function fetchBooks() {
  const box = $("#library-list");
  if (box) box.innerHTML = '<div class="muted">Carico libreria…</div>';

  try {
    const res = await fetch(`${API_BASE_URL}/books`, { method: "GET" });
    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status}${txt ? `: ${txt}` : ""}`);
    }
    const data = await res.json();
    renderLibrary(Array.isArray(data) ? data : (data?.items || []));
  } catch (e) {
    if (box) box.innerHTML = `<div class="error">Errore: ${e.message || e}</div>`;
  }
}

function renderLibrary(books) {
  const box = $("#library-list");
  if (!box) return;

  if (!books || books.length === 0) {
    box.innerHTML = `<div class="muted">Nessun libro ancora. Crea il tuo primo libro con “Crea libro”.</div>`;
    return;
  }

  box.innerHTML = "";
  books.forEach((b) => {
    const id = b?.id || b?.book_id || "";
    const title = b?.title || "(senza titolo)";
    const author = b?.author || "—";
    const lang = b?.language || "it";

    const card = document.createElement("div");
    card.className = "card";
    card.style.margin = "10px 0";
    card.innerHTML = `
      <div class="card-head">
        <strong>${escapeHtml(title)}</strong>
        <span class="badge">${escapeHtml(id)}</span>
      </div>
      <div class="muted">Autore: ${escapeHtml(author)} — Lingua: ${escapeHtml(lang)}</div>
      <div class="row-right" style="margin-top:10px">
        <button class="btn btn-secondary" data-action="open" data-bookid="${escapeAttr(id)}">Apri</button>
        <button class="btn btn-ghost" data-action="edit" data-bookid="${escapeAttr(id)}">Modifica</button>
        <button class="btn btn-ghost" data-action="delete" data-bookid="${escapeAttr(id)}">Elimina</button>
      </div>
    `;
    box.appendChild(card);
  });
}

/* ───────────────────────────────────────────────
   Azioni: crea / elimina / apri editor
   ─────────────────────────────────────────────── */
async function createBookSimple() {
  const title = prompt("Titolo del libro:", "Manuale EccomiBook");
  if (title == null) return;

  try {
    const res = await fetch(`${API_BASE_URL}/books/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: (title || "").trim() || "Senza titolo",
        author: "EccomiBook",
        language: "it",
        chapters: []
      }),
    });

    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status}${txt ? `: ${txt}` : ""}`);
    }

    const data = await res.json();
    const newId = data?.book_id || data?.id || "";
    rememberLastBook(newId);
    toast("✅ Libro creato!");

    // 👉 Mostra SUBITO la Libreria, ricarica e scrolla in vista
    await toggleLibrary(true);
    await fetchBooks();
    $("#library-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    toast("Errore di rete: " + (e?.message || e));
  }
}

async function deleteBook(bookId) {
  if (!bookId) return;
  const ok = confirm("Eliminare questo libro?");
  if (!ok) return;

  try {
    const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}`, {
      method: "DELETE",
    });
    if (!res.ok && res.status !== 204) {
      const txt = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status}${txt ? `: ${txt}` : ""}`);
    }
    toast("Libro eliminato.");
    await fetchBooks();
  } catch (e) {
    toast("Errore: " + (e?.message || e));
  }
}

function goEditor(bookId) {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "block";

  const inputBook = $("#bookIdInput");
  const inputCh = $("#chapterIdInput");
  const ta = $("#chapterText");

  const id = bookId || loadLastBook() || "";
  if (inputBook) inputBook.value = id;
  if (inputCh && !inputCh.value) inputCh.value = "ch_0001";
  if (ta && !ta.value) ta.value = "Scrivi qui il contenuto del capitolo…";
}

function closeEditor() {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "none";
}

/* ───────────────────────────────────────────────
   Libreria: toggle visibilità
   ─────────────────────────────────────────────── */
async function toggleLibrary(force) {
  const lib = $("#library-section");
  if (!lib) return;

  if (typeof force === "boolean") {
    uiState.libraryVisible = force;
  } else {
    uiState.libraryVisible = !uiState.libraryVisible;
  }
  lib.style.display = uiState.libraryVisible ? "block" : "none";

  if (uiState.libraryVisible) {
    await fetchBooks();
  }
}

/* ───────────────────────────────────────────────
   Wiring bottoni
   ─────────────────────────────────────────────── */
function wireButtons() {
  // Topbar
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", () => toggleLibrary());
  $("#btn-editor")?.addEventListener("click", () => goEditor());

  // Azioni rapide (ID dedicati)
  $("#btn-quick-create")?.addEventListener("click", createBookSimple);
  $("#btn-quick-library")?.addEventListener("click", () => toggleLibrary(true));
  $("#btn-quick-editor")?.addEventListener("click", () => goEditor());

  // Editor
  $("#btn-ed-close")?.addEventListener("click", closeEditor);
  $("#btn-ed-save")?.addEventListener("click", () => {
    toast("Demo salvataggio capitolo (endpoint reale in una prossima iterazione).");
  });

  // Delega eventi sulla libreria (Apri / Elimina / Modifica)
  $("#library-list")?.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("button[data-action]");
    if (!btn) return;

    const action = btn.getAttribute("data-action");
    const bookId = btn.getAttribute("data-bookid") || "";

    if (action === "open") {
      rememberLastBook(bookId);
      goEditor(bookId);
    } else if (action === "delete") {
      await deleteBook(bookId);
    } else if (action === "edit") {
      toast("✏️ Modifica libro: arriverà a breve.");
    }
  });
}

/* ───────────────────────────────────────────────
   Init
   ─────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();
  // Avvio: Libreria nascosta; la carico solo quando l’utente la apre
  await toggleLibrary(false);
});
