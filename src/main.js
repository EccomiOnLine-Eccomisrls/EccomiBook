/* =========================================================
 * EccomiBook — Frontend (Vite, vanilla)
 * src/main.js — COMPLETO
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

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

function toast(msg) { alert(msg); }

function rememberLastBook(id) { try { localStorage.setItem("last_book_id", id || ""); } catch {} }
function loadLastBook()       { try { return localStorage.getItem("last_book_id") || ""; } catch { return ""; } }

function setText(id, text) { const el = document.getElementById(id); if (el) el.textContent = text; }

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, m => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]
  ));
}
function escapeAttr(s) { return escapeHtml(s).replace(/"/g, "&quot;"); }

/* ───────────────────────────────────────────────
   Stato UI
   ─────────────────────────────────────────────── */
const uiState = {
  libraryVisible: true,
  booksCache: [],          // ultima libreria letta
  currentBookId: "",       // libro aperto nell’editor
  currentChapterId: "",    // capitolo aperto
};

/* ───────────────────────────────────────────────
   Backend ping + badge
   ─────────────────────────────────────────────── */
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

/* ───────────────────────────────────────────────
   Libreria: API + render
   ─────────────────────────────────────────────── */
async function fetchBooks() {
  const box = $("#library-list");
  if (box) box.innerHTML = '<div class="muted">Carico libreria…</div>';
  try {
    const res = await fetch(`${API_BASE_URL}/books?ts=${Date.now()}`, {
      method: "GET",
      cache: "no-store",
      headers: { "Accept": "application/json" },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = Array.isArray(data) ? data : (data?.items || []);
    uiState.booksCache = items;
    renderLibrary(items);
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
  const grid = document.createElement("div");
  grid.className = "library-grid";
  box.appendChild(grid);

  books.forEach((b) => {
    const id = b?.id || b?.book_id || "";
    const title = b?.title || "(senza titolo)";
    const author = b?.author || "—";
    const lang = b?.language || "it";

    const card = document.createElement("div");
    card.className = "book-card";
    card.innerHTML = `
      <div class="book-title">${escapeHtml(title)}</div>
      <div class="book-meta">Autore: ${escapeHtml(author)} — Lingua: ${escapeHtml(lang)}</div>
      <div class="book-id">${escapeHtml(id)}</div>
      <div class="row-right" style="margin-top:10px">
        <button class="btn btn-secondary" data-action="open-book" data-bookid="${escapeAttr(id)}">Apri</button>
        <button class="btn btn-ghost" data-action="edit-book" data-bookid="${escapeAttr(id)}">Modifica</button>
        <button class="btn btn-ghost" data-action="delete-book" data-bookid="${escapeAttr(id)}">Elimina</button>
      </div>
    `;
    grid.appendChild(card);
  });
}

/* ───────────────────────────────────────────────
   Capitoli — render elenco + azioni
   ─────────────────────────────────────────────── */
function findBookInCache(bookId) {
  return uiState.booksCache.find(b => (b?.id || b?.book_id) === bookId);
}

function renderChapterList(bookId) {
  const list = $("#chapters-list");
  const panel = $("#chapters-panel");
  if (!list || !panel) return;

  const book = findBookInCache(bookId);
  const chapters = (book?.chapters || []).slice(); // copia
  // ordina per id
  chapters.sort((a,b)=>String(a.id).localeCompare(String(b.id)));

  if (chapters.length === 0) {
    panel.style.display = "block";
    list.innerHTML = `<div class="muted">Nessun capitolo ancora. Scrivi e salva il primo capitolo.</div>`;
    return;
  }

  panel.style.display = "block";
  list.innerHTML = chapters.map(ch => {
    const cid = escapeHtml(ch.id || "");
    const updated = ch.updated_at ? ` · ${escapeHtml(ch.updated_at)}` : "";
    return `
      <div class="chapter-row">
        <div class="chapter-info">
          <div class="chapter-title">${cid}</div>
          <div class="chapter-meta">ID: ${cid}${updated}</div>
        </div>
        <div class="row-right">
          <button class="btn btn-secondary" data-cmd="open-chapter" data-chapter="${cid}">Apri</button>
          <button class="btn btn-ghost" data-cmd="delete-chapter" data-chapter="${cid}">Elimina</button>
          <button class="btn btn-ghost" data-cmd="dl-md" data-chapter="${cid}">MD</button>
          <button class="btn btn-ghost" data-cmd="dl-txt" data-chapter="${cid}">TXT</button>
          <button class="btn btn-ghost" data-cmd="dl-pdf" data-chapter="${cid}">PDF</button>
        </div>
      </div>
    `;
  }).join("");
}

async function loadChapterToEditor(bookId, chapterId) {
  // prova prima a leggere dal backend; se 404, svuota editor ma imposta gli ID
  const inputBook = $("#bookIdInput");
  const inputCh = $("#chapterIdInput");
  const inputTopic = $("#topicInput");
  const ta = $("#chapterText");
  const ed = $("#editor-card");

  if (ed) ed.style.display = "block";
  if (inputBook) inputBook.value = bookId || "";
  if (inputCh) inputCh.value = chapterId || "ch_0001";
  if (inputTopic && !inputTopic.value) inputTopic.value = "";

  uiState.currentBookId = bookId || "";
  uiState.currentChapterId = chapterId || "";

  let content = "";
  try {
    const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}?ts=${Date.now()}`, { cache: "no-store" });
    if (res.ok) {
      const data = await res.json();
      content = data?.content || "";
    }
  } catch {}

  if (ta) ta.value = content || "";
}

/* ───────────────────────────────────────────────
   Azioni: crea/elimina libro, salva/AI capitoli
   ─────────────────────────────────────────────── */
async function createBookSimple() {
  const title = prompt("Titolo del libro:", "Manuale EccomiBook");
  if (title == null) return;

  try {
    const res = await fetch(`${API_BASE_URL}/books/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      body: JSON.stringify({
        title: (title.trim() || "Senza titolo"),
        author: "EccomiBook",
        language: "it",
        chapters: []
      }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const newId = data?.book_id || data?.id || "";
    rememberLastBook(newId);
    toast("✅ Libro creato!");
    await toggleLibrary(true);
    await fetchBooks();
    setTimeout(fetchBooks, 300);
  } catch (e) {
    toast("Errore di rete: " + (e?.message || e));
  }
}

async function deleteBook(bookId) {
  if (!bookId) return;
  if (!confirm("Eliminare questo libro?")) return;
  try {
    const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
    toast("Libro eliminato.");
    await fetchBooks();
  } catch (e) {
    toast("Errore: " + (e?.message || e));
  }
}

async function saveChapter() {
  const bookId = $("#bookIdInput")?.value?.trim();
  const chapterId = $("#chapterIdInput")?.value?.trim() || "ch_0001";
  const content = $("#chapterText")?.value ?? "";

  if (!bookId) return toast("Seleziona un libro.");
  try {
    const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    toast("💾 Capitolo salvato.");
    await fetchBooks();                   // ricarico metadata
    renderChapterList(bookId);            // aggiorno lista visibile
  } catch (e) {
    toast("Errore salvataggio: " + (e?.message || e));
  }
}

async function writeWithAI() {
  const bookId = $("#bookIdInput")?.value?.trim();
  const chapterId = $("#chapterIdInput")?.value?.trim() || "ch_0001";
  const topic = $("#topicInput")?.value?.trim() || "";

  if (!bookId) return toast("Seleziona un libro.");
  if (!topic)  return toast("Scrivi un topic per l’AI.");

  try {
    const res = await fetch(`${API_BASE_URL}/generate/chapter`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        book_id: bookId,
        chapter_id: chapterId,
        topic,
        language: "it"
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const content = data?.content || data?.text || "";
    if (!content) return toast("AI: nessun contenuto ricevuto.");
    $("#chapterText").value = content;
    toast("✨ Testo AI inserito nell’editor. Ricorda di salvarlo.");
  } catch (e) {
    toast("Errore AI: " + (e?.message || e));
  }
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
  if (uiState.libraryVisible) await fetchBooks();
}

/* ───────────────────────────────────────────────
   Wiring bottoni
   ─────────────────────────────────────────────── */
function wireButtons() {
  // Topbar
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", () => toggleLibrary());
  $("#btn-editor")?.addEventListener("click", () => $("#editor-card").style.display = "block");

  // Azioni rapide (toggle richiesto)
  $("#btn-quick-create")?.addEventListener("click", createBookSimple);
  $("#btn-quick-library")?.addEventListener("click", () => toggleLibrary());
  $("#btn-quick-editor")?.addEventListener("click", () => $("#editor-card").style.display = "block");

  // Editor
  $("#btn-ed-close")?.addEventListener("click", () => { $("#editor-card").style.display = "none"; });
  $("#btn-ed-save")?.addEventListener("click", saveChapter);
  $("#btn-ed-ai")?.addEventListener("click", writeWithAI);

  // Libreria: delegation per i 3 bottoni della card libro
  $("#library-list")?.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("button[data-action]");
    if (!btn) return;
    const action = btn.getAttribute("data-action");
    const bookId = btn.getAttribute("data-bookid") || "";

    if (action === "open-book" || action === "edit-book") {
      rememberLastBook(bookId);
      uiState.currentBookId = bookId;
      await loadChapterToEditor(bookId, "ch_0001"); // default
      renderChapterList(bookId);
      // Mostro editor
      $("#editor-card").style.display = "block";
    } else if (action === "delete-book") {
      await deleteBook(bookId);
    }
  });

  // Capitoli: delegation (funziona anche dopo re-render)
  $("#chapters-list")?.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("button[data-cmd]");
    if (!btn) return;
    const cmd = btn.getAttribute("data-cmd");
    const chapterId = btn.getAttribute("data-chapter") || "";
    const bookId = uiState.currentBookId;

    if (!bookId) return;

    if (cmd === "open-chapter") {
      await loadChapterToEditor(bookId, chapterId);
    } else if (cmd === "delete-chapter") {
      toast("🗑️ Elimina capitolo: arriverà a breve (endpoint backend).");
    } else if (cmd === "dl-md" || cmd === "dl-txt") {
      // Provo a costruire lo static path: chapters/<book_id>/<chapter_id>.md
      const href = `${API_BASE_URL.replace(/\/+$/,"")}/static/chapters/${encodeURIComponent(bookId)}/${encodeURIComponent(chapterId)}.md`;
      window.open(href, "_blank");
    } else if (cmd === "dl-pdf") {
      toast("📄 PDF del singolo capitolo: work in progress (export capitolo).");
    }
  });
}

/* ───────────────────────────────────────────────
   Init
   ─────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();
  await toggleLibrary(true);

  // se ho un last_book, preparo l’editor al volo (qualora volessi riprendere)
  const last = loadLastBook();
  if (last) {
    uiState.currentBookId = last;
    renderChapterList(last);
  }
});
