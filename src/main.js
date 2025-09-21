/* =========================================================
 * EccomiBook — Frontend (Vite, vanilla)
 * src/main.js — COMPLETO (AI integrata)
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
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m])
  );
const escapeAttr = (s) => escapeHtml(s).replace(/"/g, "&quot;");

const toast = (m) => alert(m);

function rememberLastBook(id) {
  try { localStorage.setItem("last_book_id", id || ""); } catch {}
}
function loadLastBook() {
  try { return localStorage.getItem("last_book_id") || ""; } catch { return ""; }
}

/* ───────────────────────────────────────────────
   Stato UI
   ─────────────────────────────────────────────── */
const uiState = {
  libraryVisible: true,
  currentBookId: "",
};

/* ───────────────────────────────────────────────
   Backend ping
   ─────────────────────────────────────────────── */
async function pingBackend() {
  const el = $("#backend-status");
  if (!el) return;

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
   Libreria (lista libri)
   ─────────────────────────────────────────────── */
async function fetchBooks() {
  const box = $("#library-list");
  if (box) box.innerHTML = '<div class="muted">Carico libreria…</div>';

  try {
    const res = await fetch(`${API_BASE_URL}/books?ts=${Date.now()}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = Array.isArray(data) ? data : (data?.items || []);
    renderLibrary(items);
  } catch (e) {
    if (box) box.innerHTML = `<div class="error">Errore: ${e.message || e}</div>`;
  }
}

function renderLibrary(books) {
  const box = $("#library-list");
  if (!box) return;

  if (!books?.length) {
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
        <button class="btn btn-secondary" data-action="open" data-bookid="${escapeAttr(id)}">Apri</button>
        <button class="btn btn-ghost" data-action="edit" data-bookid="${escapeAttr(id)}">Modifica</button>
        <button class="btn btn-ghost" data-action="delete" data-bookid="${escapeAttr(id)}">Elimina</button>
      </div>
    `;
    grid.appendChild(card);
  });
}

/* ───────────────────────────────────────────────
   Sezione editor — capitoli
   ─────────────────────────────────────────────── */
function showEditor(bookId) {
  uiState.currentBookId = bookId || loadLastBook() || "";
  if (!uiState.currentBookId) return;

  rememberLastBook(uiState.currentBookId);

  $("#editor-card").style.display = "block";
  $("#bookIdInput").value = uiState.currentBookId;

  // default per nuovo capitolo
  const chInput = $("#chapterIdInput");
  if (!chInput.value) chInput.value = "ch_0001";

  // pulizia placeholder
  const ta = $("#chapterText");
  if (!ta.value) ta.value = "Scrivi qui il contenuto del capitolo…";

  // carica lista capitoli
  refreshChaptersList(uiState.currentBookId);
}

function closeEditor() {
  $("#editor-card").style.display = "none";
}

/* Lista capitoli */
async function refreshChaptersList(bookId) {
  const list = $("#chapters-list");
  if (list) list.innerHTML = '<div class="muted">Carico capitoli…</div>';

  try {
    // preferito: endpoint dedicato; in alternativa ricadi su /books e prendi .chapters
    let chapters = [];

    const r = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters?ts=${Date.now()}`, {
      cache: "no-store",
    });

    if (r.ok) {
      chapters = await r.json();
    } else {
      // fallback: prendo i libri e cerco quello giusto
      const resBooks = await fetch(`${API_BASE_URL}/books?ts=${Date.now()}`, { cache: "no-store" });
      if (resBooks.ok) {
        const all = await resBooks.json();
        const arr = Array.isArray(all) ? all : (all?.items || []);
        const found = arr.find((x) => (x?.id || x?.book_id) === bookId);
        chapters = found?.chapters || [];
      }
    }

    renderChaptersList(bookId, chapters || []);
  } catch (e) {
    if (list) list.innerHTML = `<div class="error">Errore: ${e.message || e}</div>`;
  }
}

function renderChaptersList(bookId, chapters) {
  const list = $("#chapters-list");
  if (!list) return;

  if (!chapters?.length) {
    list.innerHTML = `<div class="muted">Nessun capitolo ancora.</div>`;
    return;
  }

  list.innerHTML = "";
  chapters.forEach((ch) => {
    const cid = ch?.id || "";
    const updated = ch?.updated_at || "";
    const li = document.createElement("div");
    li.className = "card";
    li.style.margin = "8px 0";
    li.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px">
        <div>
          <div style="font-weight:600">${escapeHtml(cid)}</div>
          <div class="muted">ID: ${escapeHtml(cid)}${updated ? ` · ${escapeHtml(updated)}` : ""}</div>
        </div>
        <div class="row-right">
          <button class="btn btn-secondary" data-ch-open="${escapeAttr(cid)}">Apri</button>
          <button class="btn btn-ghost" data-ch-del="${escapeAttr(cid)}">Elimina</button>
          <a class="btn btn-ghost" href="${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(cid)}/md" target="_blank" rel="noreferrer">MD</a>
          <a class="btn btn-ghost" href="${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(cid)}/txt" target="_blank" rel="noreferrer">TXT</a>
          <a class="btn btn-ghost" href="${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(cid)}/pdf" target="_blank" rel="noreferrer">PDF</a>
        </div>
      </div>
    `;
    list.appendChild(li);
  });
}

/* Apri un capitolo dalla lista */
async function openChapter(bookId, chapterId) {
  try {
    const r = await fetch(
      `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}?ts=${Date.now()}`,
      { cache: "no-store" }
    );
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();

    $("#bookIdInput").value = bookId;
    $("#chapterIdInput").value = chapterId;
    $("#chapterText").value = data?.content || "";
  } catch (e) {
    toast("Impossibile aprire il capitolo: " + (e?.message || e));
  }
}

/* Elimina capitolo */
async function deleteChapter(bookId, chapterId) {
  if (!confirm(`Eliminare il capitolo ${chapterId}?`)) return;
  try {
    const r = await fetch(
      `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`,
      { method: "DELETE" }
    );
    if (!r.ok && r.status !== 204) throw new Error(`HTTP ${r.status}`);
    toast("Capitolo eliminato.");
    refreshChaptersList(bookId);
  } catch (e) {
    toast("Errore eliminazione: " + (e?.message || e));
  }
}

/* Salva capitolo corrente (PUT upsert) */
async function saveCurrentChapter() {
  const bookId = $("#bookIdInput").value.trim();
  const chapterId = $("#chapterIdInput").value.trim();
  const content = $("#chapterText").value;

  if (!bookId || !chapterId) {
    toast("Inserisci Book ID e Chapter ID.");
    return;
  }

  try {
    const r = await fetch(
      `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      }
    );
    if (!r.ok) {
      const t = await r.text().catch(() => "");
      throw new Error(`HTTP ${r.status}${t ? `: ${t}` : ""}`);
    }
    toast("💾 Capitolo salvato.");
    refreshChaptersList(bookId);
  } catch (e) {
    toast("Errore salvataggio: " + (e?.message || e));
  }
}

/* Scrittura con AI */
async function generateWithAI() {
  const bookId = $("#bookIdInput").value.trim() || uiState.currentBookId;
  const chapterId = $("#chapterIdInput").value.trim();
  const topic = $("#topicInput")?.value?.trim() || "";

  if (!bookId || !chapterId) {
    toast("Inserisci Book ID e Chapter ID.");
    return;
  }

  try {
    // 1) genera testo
    const r = await fetch(`${API_BASE_URL}/generate/chapter`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ book_id: bookId, chapter_id: chapterId, topic }),
    });
    if (!r.ok) {
      const t = await r.text().catch(() => "");
      throw new Error(`HTTP ${r.status}${t ? `: ${t}` : ""}`);
    }
    const data = await r.json();
    $("#chapterText").value = data?.content || "";

    // 2) salva subito (opzionale ma comodo)
    await saveCurrentChapter();
  } catch (e) {
    toast("Errore AI: " + (e?.message || e));
  }
}

/* ───────────────────────────────────────────────
   Libreria: toggle
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
   Azioni globali
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
        chapters: [],
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
  if (!confirm("Eliminare il libro?")) return;
  try {
    const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}`, {
      method: "DELETE",
    });
    if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
    toast("Libro eliminato.");
    await fetchBooks();
  } catch (e) {
    toast("Errore: " + (e?.message || e));
  }
}

/* ───────────────────────────────────────────────
   Wiring
   ─────────────────────────────────────────────── */
function wireButtons() {
  // Topbar
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", () => toggleLibrary());
  $("#btn-editor")?.addEventListener("click", () => showEditor(loadLastBook()));

  // Azioni rapide (toggle richiesto)
  $("#btn-quick-create")?.addEventListener("click", createBookSimple);
  $("#btn-quick-library")?.addEventListener("click", () => toggleLibrary());
  $("#btn-quick-editor")?.addEventListener("click", () => showEditor(loadLastBook()));

  // Editor
  $("#btn-ed-close")?.addEventListener("click", closeEditor);
  $("#btn-ed-save")?.addEventListener("click", saveCurrentChapter);
  $("#btn-ai-generate")?.addEventListener("click", generateWithAI);

  // Elimina capitolo (pulsante dentro editor, per l’ID attuale)
  $("#btn-ed-delete")?.addEventListener("click", async () => {
    const bookId = $("#bookIdInput").value.trim();
    const chapterId = $("#chapterIdInput").value.trim();
    if (!bookId || !chapterId) return toast("Inserisci Book ID e Chapter ID.");
    await deleteChapter(bookId, chapterId);
  });

  // Deleghe su lista LIBRI (Apri/Elimina/Modifica)
  $("#library-list")?.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("button[data-action]");
    if (!btn) return;
    const action = btn.getAttribute("data-action");
    const bookId = btn.getAttribute("data-bookid") || "";
    if (!bookId) return;

    if (action === "open") {
      rememberLastBook(bookId);
      showEditor(bookId);
    } else if (action === "delete") {
      await deleteBook(bookId);
    } else if (action === "edit") {
      toast("✏️ Modifica libro: in arrivo.");
    }
  });

  // Deleghe su lista CAPITOLI
  $("#chapters-list")?.addEventListener("click", async (ev) => {
    const openBtn = ev.target.closest("[data-ch-open]");
    const delBtn  = ev.target.closest("[data-ch-del]");
    if (!openBtn && !delBtn) return;

    const cid = (openBtn || delBtn).getAttribute(openBtn ? "data-ch-open" : "data-ch-del");
    const bid = uiState.currentBookId || $("#bookIdInput").value.trim();
    if (!cid || !bid) return;

    if (openBtn) {
      await openChapter(bid, cid);
    } else if (delBtn) {
      await deleteChapter(bid, cid);
    }
  });
}

/* ───────────────────────────────────────────────
   Init
   ─────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();
  await toggleLibrary(true); // mostra e carica la libreria all’avvio
});
