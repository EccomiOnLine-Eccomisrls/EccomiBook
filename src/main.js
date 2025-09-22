/* =========================================================
 * EccomiBook — Frontend (Vite, vanilla)
 * src/main.js — v2.1 (nav capitoli, autosave smart, export)
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
   Helpers
   ─────────────────────────────────────────────── */
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const escapeHtml = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (m) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m]
  ));
const escapeAttr = (s) => escapeHtml(s).replace(/"/g, "&quot;");

const toast = (m) => alert(m);

function rememberLastBook(id) { try { localStorage.setItem("last_book_id", id || ""); } catch {} }
function loadLastBook()      { try { return localStorage.getItem("last_book_id") || ""; } catch { return ""; } }

/* ───────────────────────────────────────────────
   UI state
   ─────────────────────────────────────────────── */
const uiState = {
  libraryVisible: true,
  currentBookId: "",
  chapters: [],                 // [{id,title?,updated_at?,path?}]
  currentChapterId: "",
  autosaveTimer: null,          // 30s
  lastSavedSnapshot: "",
  saveSoon: null,               // autosave “debounced” 1.5s dopo input
};

/* ───────────────────────────────────────────────
   Backend ping
   ─────────────────────────────────────────────── */
async function pingBackend() {
  const el = $("#backend-status"); if (!el) return;
  el.textContent = "Backend: verifico…";
  try {
    const r = await fetch(`${API_BASE_URL}/health`, { cache: "no-store" });
    el.textContent = r.ok ? "Backend: ✅ OK" : `Backend: errore ${r.status}`;
  } catch {
    el.textContent = "Backend: non raggiungibile";
  }
  const dbg = document.createElement("div");
  dbg.className = "debug-url";
  dbg.innerHTML = `API: <a href="${API_BASE_URL}" target="_blank" rel="noreferrer">${API_BASE_URL}</a>`;
  el.appendChild(dbg);
}

/* ───────────────────────────────────────────────
   Libreria
   ─────────────────────────────────────────────── */
async function fetchBooks() {
  const box = $("#library-list");
  if (box) box.innerHTML = '<div class="muted">Carico libreria…</div>';

  try {
    const res = await fetch(`${API_BASE_URL}/books?ts=${Date.now()}`, {
      cache: "no-store", headers: { Accept: "application/json" },
    });
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
  const box = $("#library-list"); if (!box) return;

  if (!books?.length) {
    box.innerHTML = `<div class="muted">Nessun libro ancora. Crea il tuo primo libro con “Crea libro”.</div>`;
    return;
  }

  box.innerHTML = "";
  const grid = document.createElement("div");
  grid.className = "library-grid";
  box.appendChild(grid);

  books.forEach((b) => {
    const id     = b?.id || b?.book_id || "";
    const title  = b?.title || "(senza titolo)";
    const author = b?.author || "—";
    const lang   = b?.language || "it";

    const card = document.createElement("div");
    card.className = "book-card";
    card.innerHTML = `
      <div class="book-title">${escapeHtml(title)}</div>
      <div class="book-meta">Autore: ${escapeHtml(author)} — Lingua: ${escapeHtml(lang)}</div>
      <div class="book-id">${escapeHtml(id)}</div>
      <div class="row-right" style="margin-top:10px;justify-content:flex-start;gap:8px">
        <button class="btn btn-secondary" data-action="open"   data-bookid="${escapeAttr(id)}">Apri</button>
        <button class="btn btn-ghost"     data-action="rename" data-bookid="${escapeAttr(id)}" data-oldtitle="${escapeAttr(title)}">Modifica</button>
        <button class="btn btn-ghost"     data-action="export" data-bookid="${escapeAttr(id)}">Scarica</button>
        <button class="btn btn-ghost"     data-action="delete" data-bookid="${escapeAttr(id)}">Elimina</button>
      </div>`;
    grid.appendChild(card);
  });
}

/* ───────────────────────────────────────────────
   Editor / Capitoli
   ─────────────────────────────────────────────── */
function showEditor(bookId) {
  uiState.currentBookId = bookId || loadLastBook() || "";
  if (!uiState.currentBookId) return;

  rememberLastBook(uiState.currentBookId);
  $("#editor-card").style.display = "block";
  $("#bookIdInput").value = uiState.currentBookId;

  // default nuovo capitolo
  const chInput = $("#chapterIdInput");
  if (!chInput.value) chInput.value = "ch_0001";

  const ta = $("#chapterText");
  if (!ta.value) ta.value = "Scrivi qui il contenuto del capitolo…";

  uiState.currentChapterId  = chInput.value.trim();
  uiState.lastSavedSnapshot = ta.value;

  refreshChaptersList(uiState.currentBookId).then(() => {
    const exists = uiState.chapters.some(c => c.id === uiState.currentChapterId);
    if (exists) openChapter(uiState.currentBookId, uiState.currentChapterId);
  });

  startAutosave();
}

function closeEditor() {
  stopAutosave();
  $("#editor-card").style.display = "none";
}

/* carica l’elenco capitoli dal /books */
async function refreshChaptersList(bookId) {
  const list = $("#chapters-list");
  if (list) list.innerHTML = '<div class="muted">Carico capitoli…</div>';

  try {
    const r = await fetch(`${API_BASE_URL}/books?ts=${Date.now()}`, { cache: "no-store" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);

    const all  = await r.json();
    const arr  = Array.isArray(all) ? all : (all?.items || []);
    const found = arr.find(x => (x?.id || x?.book_id) === bookId);
    const chapters = found?.chapters || [];

    uiState.chapters = chapters.map(c => ({
      id: c?.id || "",
      title: c?.title || c?.id || "",
      updated_at: c?.updated_at || "",
      path: c?.path || ""
    }));

    renderChaptersList(bookId, uiState.chapters);
  } catch (e) {
    if (list) list.innerHTML = `<div class="error">Errore: ${e.message || e}</div>`;
  }
}

/* render capitoli con pulsanti sotto (mobile-friendly) */
function renderChaptersList(bookId, chapters) {
  const list = $("#chapters-list"); if (!list) return;

  if (!chapters?.length) {
    list.innerHTML = `<div class="muted">Nessun capitolo ancora.</div>`;
    return;
  }

  list.innerHTML = "";

  // nav prev/next
  const nav = document.createElement("div");
  nav.className = "row-right";
  nav.style.justifyContent = "flex-start";
  nav.style.marginBottom    = "8px";
  nav.innerHTML = `
    <button class="btn btn-ghost" id="btn-ch-prev">← Precedente</button>
    <button class="btn btn-ghost" id="btn-ch-next">Successivo →</button>`;
  list.appendChild(nav);

  chapters.forEach((ch) => {
    const cid     = ch.id;
    const updated = ch.updated_at || "";

    const li = document.createElement("div");
    li.className = "card chapter-row";
    li.style.margin = "8px 0";

    li.innerHTML = `
      <div class="chapter-head">
        <div>
          <div style="font-weight:600">${escapeHtml(ch.title || cid)}</div>
          <div class="muted">ID: ${escapeHtml(cid)}${updated ? ` · ${escapeHtml(updated)}` : ""}</div>
        </div>
      </div>

      <div class="chapter-actions">
        <button class="btn btn-secondary" data-ch-open="${escapeAttr(cid)}">Apri</button>
        <button class="btn btn-ghost"     data-ch-edit="${escapeAttr(cid)}">Modifica</button>
        <button class="btn btn-ghost"     data-ch-del="${escapeAttr(cid)}">Elimina</button>
        <button class="btn btn-ghost"     data-ch-dl="${escapeAttr(cid)}">Scarica</button>
      </div>`;
    list.appendChild(li);
  });

  $("#btn-ch-prev")?.addEventListener("click", () => stepChapter(-1));
  $("#btn-ch-next")?.addEventListener("click", () => stepChapter(+1));
}

function chapterIndex(cid) { return uiState.chapters.findIndex(c => c.id === cid); }

function stepChapter(delta) {
  if (!uiState.chapters.length) return;
  const idx   = chapterIndex(uiState.currentChapterId);
  const next  = Math.min(Math.max(idx + delta, 0), uiState.chapters.length - 1);
  const target = uiState.chapters[next]?.id;
  if (target && target !== uiState.currentChapterId) {
    maybeAutosaveNow().finally(() => openChapter(uiState.currentBookId, target));
  }
}

async function openChapter(bookId, chapterId) {
  try {
    const r = await fetch(
      `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}?ts=${Date.now()}`,
      { cache: "no-store" }
    );
    if (!r.ok) throw new Error(`HTTP ${r.status}`);

    const data = await r.json();

    $("#bookIdInput").value    = bookId;
    $("#chapterIdInput").value = chapterId;
    $("#chapterText").value    = data?.content || "";

    uiState.currentBookId      = bookId;
    uiState.currentChapterId   = chapterId;
    uiState.lastSavedSnapshot  = $("#chapterText").value;

    toast(`📖 Aperto ${chapterId}`);
  } catch (e) {
    toast("Impossibile aprire il capitolo: " + (e?.message || e));
  }
}

async function deleteChapter(bookId, chapterId) {
  if (!confirm(`Eliminare il capitolo ${chapterId}?`)) return;
  try {
    const r = await fetch(
      `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`,
      { method: "DELETE" }
    );
    if (!r.ok && r.status !== 204) throw new Error(`HTTP ${r.status}`);

    toast("🗑️ Capitolo eliminato.");
    await refreshChaptersList(bookId);

    if (uiState.currentChapterId === chapterId) {
      $("#chapterText").value = "";
      uiState.currentChapterId = "";
    }
  } catch (e) {
    toast("Errore eliminazione: " + (e?.message || e));
  }
}

function editChapter(cid) {
  $("#chapterIdInput").value = cid;
  uiState.currentChapterId   = cid;
  openChapter(uiState.currentBookId, cid).then(() => $("#chapterText")?.focus());
}

async function saveCurrentChapter(showToast = true) {
  const bookId    = $("#bookIdInput").value.trim();
  const chapterId = $("#chapterIdInput").value.trim();
  const content   = $("#chapterText").value;

  if (!bookId || !chapterId) return toast("Inserisci Book ID e Chapter ID.");

  try {
    const r = await fetch(
      `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`,
      { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content }) }
    );
    if (!r.ok) {
      const t = await r.text().catch(() => "");
      throw new Error(`HTTP ${r.status}${t ? `: ${t}` : ""}`);
    }

    uiState.lastSavedSnapshot = content;
    if (showToast) toast("✅ Capitolo salvato.");
    refreshChaptersList(bookId);
  } catch (e) {
    toast("Errore salvataggio: " + (e?.message || e));
  }
}

/* ─ Autosave ─ */
function startAutosave()  { stopAutosave(); uiState.autosaveTimer = setInterval(maybeAutosaveNow, 30_000); }
function stopAutosave()   { if (uiState.autosaveTimer) clearInterval(uiState.autosaveTimer); uiState.autosaveTimer = null; }
async function maybeAutosaveNow() {
  const txt = $("#chapterText")?.value ?? "";
  if (txt !== uiState.lastSavedSnapshot && uiState.currentBookId && uiState.currentChapterId) {
    await saveCurrentChapter(false);
  }
}

/* ─ AI ─ */
async function generateWithAI() {
  const bookId    = $("#bookIdInput").value.trim() || uiState.currentBookId;
  const chapterId = $("#chapterIdInput").value.trim();
  const topic     = $("#topicInput")?.value?.trim() || "";

  if (!bookId || !chapterId) return toast("Inserisci Book ID e Chapter ID.");

  try {
    const r = await fetch(`${API_BASE_URL}/generate/chapter`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ book_id: bookId, chapter_id: chapterId, topic }),
    });
    if (!r.ok) {
      const t = await r.text().catch(() => "");
      throw new Error(`HTTP ${r.status}${t ? `: ${t}` : ""}`);
    }
    const data = await r.json();
    $("#chapterText").value = data?.content || data?.text || "";
    toast("✨ Testo generato (bozza).");

    await saveCurrentChapter(false);
    await refreshChaptersList(bookId);
  } catch (e) {
    toast("⚠️ AI di test: " + (e?.message || e));
  }
}

/* ─ Export ─ */
function askFormat(defaultFmt = "pdf") {
  const ans = prompt("Formato? (pdf / md / txt)", defaultFmt)?.trim().toLowerCase();
  if (!ans) return null;
  if (!["pdf", "md", "txt"].includes(ans)) { toast("Formato non valido."); return null; }
  return ans;
}

function downloadChapter(bookId, chapterId) {
  const fmt = askFormat("pdf"); if (!fmt) return;
  // FIX corretto: endpoint a “/…/<fmt>” (non con il punto)
  const url = `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}/${fmt}`;
  window.open(url, "_blank", "noopener");
}

async function exportBook(bookId) {
  const fmt = askFormat("pdf"); if (!fmt) return;

  if (fmt === "pdf") {
    // placeholder (quando avremo l’endpoint di export libro)
    try {
      const r = await fetch(`${API_BASE_URL}/generate/export/book/${encodeURIComponent(bookId)}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      const url  = data?.download_url || data?.url;
      return url ? window.open(url, "_blank", "noopener") : toast("Export avviato ma nessun URL ricevuto.");
    } catch (e) { toast("Errore export PDF: " + (e?.message || e)); }
  } else {
    // assemble MD/TXT lato client
    try {
      await refreshChaptersList(bookId);
      if (!uiState.chapters.length) return toast("Nessun capitolo da esportare.");

      let assembled = `# ${bookId}\n\n`;
      for (const ch of uiState.chapters) {
        const resp = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(ch.id)}`, { cache: "no-store" });
        const data = resp.ok ? await resp.json() : { content: "" };
        assembled += `\n\n# ${ch.title || ch.id}\n\n${data.content || ""}\n`;
      }
      const mime = fmt === "md" ? "text/markdown" : "text/plain";
      const blob = new Blob([assembled], { type: `${mime};charset=utf-8` });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${bookId}.${fmt}`;
      a.click();
      URL.revokeObjectURL(a.href);
    } catch (e) { toast("Errore export: " + (e?.message || e)); }
  }
}

/* ─ Libreria: toggle ─ */
async function toggleLibrary(force) {
  const lib = $("#library-section"); if (!lib) return;
  uiState.libraryVisible = (typeof force === "boolean") ? force : !uiState.libraryVisible;
  lib.style.display = uiState.libraryVisible ? "block" : "none";
  if (uiState.libraryVisible) await fetchBooks();
}

/* ─ Azioni globali ─ */
async function createBookSimple() {
  const title = prompt("Titolo del libro:", "Manuale EccomiBook");
  if (title == null) return;

  try {
    const res = await fetch(`${API_BASE_URL}/books/create`, {
      method: "POST", headers: { "Content-Type": "application/json" }, cache: "no-store",
      body: JSON.stringify({ title: (title.trim() || "Senza titolo"), author: "EccomiBook", language: "it", chapters: [] }),
    });
    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status}${txt ? `: ${txt}` : ""}`);
    }
    const data = await res.json();
    rememberLastBook(data?.book_id || data?.id || "");
    toast("✅ Libro creato!");
    await toggleLibrary(true);
    await fetchBooks();
    setTimeout(fetchBooks, 300);
  } catch (e) { toast("Errore di rete: " + (e?.message || e)); }
}

async function deleteBook(bookId) {
  if (!confirm("Eliminare il libro?")) return;
  try {
    const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
    toast("🗑️ Libro eliminato.");
    await fetchBooks();
  } catch (e) { toast("Errore: " + (e?.message || e)); }
}

async function renameBook(bookId, oldTitle) {
  const newTitle = prompt("Nuovo titolo libro:", oldTitle || "")?.trim();
  if (!newTitle || newTitle === oldTitle) return;
  // TODO: endpoint rename; per ora solo feedback
  toast("✏️ Titolo modificato (endpoint reale in arrivo).");
}

/* ─ Wiring ─ */
function wireButtons() {
  // Topbar
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", () => toggleLibrary());
  $("#btn-editor")?.addEventListener("click", () => showEditor(loadLastBook()));

  // Azioni rapide
  $("#btn-quick-create")?.addEventListener("click", createBookSimple);
  $("#btn-quick-library")?.addEventListener("click", () => toggleLibrary());
  $("#btn-quick-editor")?.addEventListener("click", () => showEditor(loadLastBook()));

  // Editor
  $("#btn-ed-close")?.addEventListener("click", closeEditor);
  $("#btn-ed-save")?.addEventListener("click", () => saveCurrentChapter(true));
  $("#btn-ai-generate")?.addEventListener("click", generateWithAI);
  $("#btn-ed-delete")?.addEventListener("click", async () => {
    const bookId    = $("#bookIdInput").value.trim();
    const chapterId = $("#chapterIdInput").value.trim();
    if (!bookId || !chapterId) return toast("Inserisci Book ID e Chapter ID.");
    await deleteChapter(bookId, chapterId);
  });

  // autosave “debounced” mentre scrivi
  $("#chapterText")?.addEventListener("input", () => {
    if (uiState.saveSoon) clearTimeout(uiState.saveSoon);
    uiState.saveSoon = setTimeout(maybeAutosaveNow, 1500);
  });

  $("#chapterIdInput")?.addEventListener("change", async () => {
    await maybeAutosaveNow();
    uiState.currentChapterId  = $("#chapterIdInput").value.trim();
    uiState.lastSavedSnapshot = $("#chapterText").value;
  });

  // Deleghe LIBRI
  $("#library-list")?.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("button[data-action]"); if (!btn) return;
    const action = btn.getAttribute("data-action");
    const bookId = btn.getAttribute("data-bookid") || "";
    if (!bookId) return;

    if (action === "open")      { rememberLastBook(bookId); showEditor(bookId); }
    else if (action === "delete"){ await deleteBook(bookId); }
    else if (action === "rename"){ await renameBook(bookId, btn.getAttribute("data-oldtitle") || ""); }
    else if (action === "export"){ await exportBook(bookId); }
  });

  // Deleghe CAPITOLI
  $("#chapters-list")?.addEventListener("click", async (ev) => {
    const openBtn = ev.target.closest("[data-ch-open]");
    const editBtn = ev.target.closest("[data-ch-edit]");
    const delBtn  = ev.target.closest("[data-ch-del]");
    const dlBtn   = ev.target.closest("[data-ch-dl]");
    if (!openBtn && !delBtn && !editBtn && !dlBtn) return;

    const cid = (openBtn || delBtn || editBtn || dlBtn).getAttribute(
      openBtn ? "data-ch-open" : delBtn ? "data-ch-del" : editBtn ? "data-ch-edit" : "data-ch-dl"
    );
    const bid = uiState.currentBookId || $("#bookIdInput").value.trim();
    if (!cid || !bid) return;

    if (openBtn)      await openChapter(bid, cid);
    else if (delBtn)  await deleteChapter(bid, cid);
    else if (editBtn) editChapter(cid);
    else if (dlBtn)   downloadChapter(bid, cid);
  });
}

/* ─ Init ─ */
document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();
  await toggleLibrary(true);
});
