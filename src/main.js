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

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function toast(msg) {
  alert(msg); // MVP
}

function rememberLastBook(id) {
  try { localStorage.setItem("last_book_id", id || ""); } catch {}
}
function loadLastBook() {
  try { return localStorage.getItem("last_book_id") || ""; } catch { return ""; }
}

// escape
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, m => (
    {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]
  ));
}
function escapeAttr(s) { return escapeHtml(s).replace(/"/g, "&quot;"); }

/* ───────────────────────────────────────────────
   Stato UI
   ─────────────────────────────────────────────── */
const uiState = { libraryVisible: true };

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
  const box = document.getElementById("library-list");
  if (box) box.innerHTML = '<div class="muted">Carico libreria…</div>';

  try {
    const res = await fetch(`${API_BASE_URL}/books?ts=${Date.now()}`, {
      method: "GET",
      cache: "no-store",
      headers: { "Accept": "application/json" },
    });

    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status}${txt ? `: ${txt}` : ""}`);
    }

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
        <button class="btn btn-secondary" data-action="open" data-bookid="${escapeAttr(id)}">Apri</button>
        <button class="btn btn-ghost" data-action="edit" data-bookid="${escapeAttr(id)}">Modifica</button>
        <button class="btn btn-ghost" data-action="delete" data-bookid="${escapeAttr(id)}">Elimina</button>
      </div>
    `;
    grid.appendChild(card);
  });
}

/* ───────────────────────────────────────────────
   Book/Chapter helpers
   ─────────────────────────────────────────────── */
async function fetchBook(bookId) {
  const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}?ts=${Date.now()}`, {
    cache: "no-store"
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

async function readChapter(bookId, chapterId) {
  const url = `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}?ts=${Date.now()}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

async function saveChapterApi(bookId, chapterId, content) {
  const url = `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`;
  const res = await fetch(url, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    body: JSON.stringify({ content }),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}${txt ? `: ${txt}` : ""}`);
  }
  return await res.json();
}

async function deleteChapterApi(bookId, chapterId) {
  const url = `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`;
  const res = await fetch(url, { method: "DELETE" });
  if (!res.ok && res.status !== 204) {
    const txt = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}${txt ? `: ${txt}` : ""}`);
  }
}

function downloadChapter(bookId, chapterId, fmt) {
  const url = `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}/export?fmt=${encodeURIComponent(fmt)}`;
  window.open(url, "_blank");
}

async function generateAI(bookId, chapterId, topic, language="it") {
  const url = `${API_BASE_URL}/generate/chapter`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
    body: JSON.stringify({ book_id: bookId, chapter_id: chapterId, topic, language }),
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}${txt ? `: ${txt}` : ""}`);
  }
  return await res.json();
}

/* ───────────────────────────────────────────────
   Libreria: azioni
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

    if (!res.ok) {
      const txt = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status}${txt ? `: ${txt}` : ""}`);
    }

    const data = await res.json();
    const newId = data?.book_id || data?.id || "";
    rememberLastBook(newId);

    alert("✅ Libro creato!");
    await toggleLibrary(true);
    await fetchBooks();
    setTimeout(fetchBooks, 300);
  } catch (e) {
    alert("Errore di rete: " + (e?.message || e));
  }
}

async function deleteBook(bookId) {
  if (!bookId) return;
  const ok = confirm("Eliminare questo libro?");
  if (!ok) return;

  try {
    await deleteChapterApi; // no-op; per coerenza lint
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

/* ───────────────────────────────────────────────
   Editor: UI
   ─────────────────────────────────────────────── */
function renderChapterList(book) {
  const body = $("#chapter-list-body");
  if (!body) return;
  const chapters = Array.isArray(book?.chapters) ? book.chapters : [];
  if (chapters.length === 0) {
    body.innerHTML = `<div class="muted">Nessun capitolo ancora. Salva il primo con l’ID (es. <code>ch_0001</code>).</div>`;
    return;
  }
  body.innerHTML = "";
  chapters.forEach(ch => {
    const id = ch?.id || "";
    const row = document.createElement("div");
    row.style.display = "flex";
    row.style.justifyContent = "space-between";
    row.style.alignItems = "center";
    row.style.padding = "6px 0";
    row.style.borderBottom = "1px solid #22324a";
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(ch.title || id)}</strong>
        <div class="muted" style="font-size:12px">ID: ${escapeHtml(id)} ${ch.updated_at ? `• ${escapeHtml(ch.updated_at)}` : ""}</div>
      </div>
      <div style="display:flex; gap:6px;">
        <button class="btn btn-ghost" data-ch-act="open" data-ch-id="${escapeAttr(id)}">Apri</button>
        <button class="btn btn-ghost" data-ch-act="del" data-ch-id="${escapeAttr(id)}">Elimina</button>
        <button class="btn btn-ghost" data-ch-act="md"  data-ch-id="${escapeAttr(id)}">MD</button>
        <button class="btn btn-ghost" data-ch-act="txt" data-ch-id="${escapeAttr(id)}">TXT</button>
        <button class="btn btn-ghost" data-ch-act="pdf" data-ch-id="${escapeAttr(id)}">PDF</button>
      </div>
    `;
    body.appendChild(row);
  });

  body.addEventListener("click", async (ev) => {
    const btn = ev.target.closest("button[data-ch-act]");
    if (!btn) return;
    const act = btn.getAttribute("data-ch-act");
    const id  = btn.getAttribute("data-ch-id");
    const bookId = $("#bookIdInput")?.value?.trim();
    if (!bookId || !id) return;

    if (act === "open") {
      $("#chapterIdInput").value = id;
      try {
        const { content } = await readChapter(bookId, id);
        $("#chapterText").value = content || "";
      } catch { alert("Impossibile leggere il capitolo."); }
    } else if (act === "del") {
      const ok = confirm(`Eliminare il capitolo ${id}?`);
      if (!ok) return;
      try {
        await deleteChapterApi(bookId, id);
        const updated = await fetchBook(bookId);
        renderChapterList(updated);
        if ($("#chapterIdInput").value === id) {
          $("#chapterText").value = "";
        }
      } catch (e) { alert("Errore eliminazione: " + (e?.message || e)); }
    } else if (["md","txt","pdf"].includes(act)) {
      downloadChapter(bookId, id, act);
    }
  }, { once: true });
}

async function goEditor(bookId) {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "block";

  const inputBook = $("#bookIdInput");
  const inputCh   = $("#chapterIdInput");
  const ta        = $("#chapterText");

  const id = bookId || loadLastBook() || "";
  if (!id) { alert("Nessun ID libro. Apri dall'elenco oppure inseriscilo."); return; }

  if (inputBook) inputBook.value = id;

  try {
    const book = await fetchBook(id);
    renderChapterList(book);
  } catch {
    renderChapterList({ id, chapters: [] });
  }

  const chId = (inputCh?.value?.trim()) || "ch_0001";
  if (inputCh) inputCh.value = chId;

  try {
    const { exists, content } = await readChapter(id, chId);
    if (ta) ta.value = exists ? content : "";
  } catch {
    if (ta) ta.value = "";
  }
}

function closeEditor() {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "none";
}

async function saveCurrentChapter() {
  const bookId = $("#bookIdInput")?.value?.trim();
  const chId   = $("#chapterIdInput")?.value?.trim();
  const text   = $("#chapterText")?.value ?? "";
  if (!bookId || !chId) return alert("Inserisci ID libro e ID capitolo.");

  try {
    await saveChapterApi(bookId, chId, text);
    alert("✅ Capitolo salvato!");
    const book = await fetchBook(bookId);
    renderChapterList(book);
  } catch (e) {
    alert("❌ Errore salvataggio — " + (e?.message || e));
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
  $("#btn-editor")?.addEventListener("click", () => goEditor());

  // Azioni rapide (IDs richiesti)
  $("#btn-quick-create")?.addEventListener("click", createBookSimple);
  $("#btn-quick-library")?.addEventListener("click", () => toggleLibrary()); // toggle, non forzato
  $("#btn-quick-editor")?.addEventListener("click", () => goEditor());

  // Editor
  $("#btn-ed-close")?.addEventListener("click", closeEditor);
  $("#btn-ed-save")?.addEventListener("click", saveCurrentChapter);
  $("#btn-ed-delete")?.addEventListener("click", async () => {
    const bookId = $("#bookIdInput")?.value?.trim();
    const chId   = $("#chapterIdInput")?.value?.trim();
    if (!bookId || !chId) return;
    const ok = confirm(`Eliminare il capitolo ${chId}?`);
    if (!ok) return;
    try {
      await deleteChapterApi(bookId, chId);
      const book = await fetchBook(bookId);
      renderChapterList(book);
      $("#chapterText").value = "";
    } catch (e) { alert("Errore eliminazione: " + (e?.message || e)); }
  });

  $("#btn-dl-md")?.addEventListener("click", () => {
    const bookId = $("#bookIdInput")?.value?.trim();
    const chId   = $("#chapterIdInput")?.value?.trim();
    if (bookId && chId) downloadChapter(bookId, chId, "md");
  });
  $("#btn-dl-txt")?.addEventListener("click", () => {
    const bookId = $("#bookIdInput")?.value?.trim();
    const chId   = $("#chapterIdInput")?.value?.trim();
    if (bookId && chId) downloadChapter(bookId, chId, "txt");
  });
  $("#btn-dl-pdf")?.addEventListener("click", () => {
    const bookId = $("#bookIdInput")?.value?.trim();
    const chId   = $("#chapterIdInput")?.value?.trim();
    if (bookId && chId) downloadChapter(bookId, chId, "pdf");
  });

  $("#btn-ai-generate")?.addEventListener("click", async () => {
    const bookId = $("#bookIdInput")?.value?.trim();
    const chId   = $("#chapterIdInput")?.value?.trim() || "ch_0001";
    const topic  = $("#topicInput")?.value?.trim() || "Capitolo";
    if (!bookId) return alert("Inserisci/Seleziona il libro.");

    try {
      const res = await generateAI(bookId, chId, topic, "it");
      $("#chapterText").value = res?.content || "";
      rememberLastBook(bookId);
      toast("✨ Testo generato. Puoi modificarlo e salvare.");
    } catch (e) {
      alert("Errore generazione: " + (e?.message || e));
    }
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
  await toggleLibrary(true);
});
