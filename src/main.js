/* =========================================================
 * EccomiBook — Frontend (Vite, vanilla)
 * src/main.js — COMPLETO
 * ========================================================= */

import "./styles.css";

/* Config */
const API_BASE_URL =
  (import.meta?.env?.VITE_API_BASE_URL) ||
  window.VITE_API_BASE_URL ||
  "https://eccomibook-backend.onrender.com";

/* Util */
const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const setText = (id, t) => { const el = document.getElementById(id); if (el) el.textContent = t; };
const toast = (m) => alert(m);

const escapeHtml = (s) => String(s ?? "").replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const escapeAttr = (s) => escapeHtml(s).replace(/"/g, "&quot;");

function rememberLastBook(id) { try { localStorage.setItem("last_book_id", id || ""); } catch {} }
function loadLastBook() { try { return localStorage.getItem("last_book_id") || ""; } catch { return ""; } }

/* Stato UI */
const uiState = { libraryVisible: true };

/* Backend ping */
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

/* Libreria */
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

/* Capitoli: pannello + operazioni */
function showEditor(show = true){ const ed = $("#editor-card"); if (ed) ed.style.display = show ? "block" : "none"; }
function showChaptersPanel(show = true){ const p = $("#chapters-panel"); if (p) p.style.display = show ? "block" : "none"; }

function setExportLinks(bookId, chapterId){
  const safeB = encodeURIComponent(bookId);
  const safeC = encodeURIComponent(chapterId);
  const md  = $("#btn-exp-md");  if (md)  md.href  = `${API_BASE_URL}/books/${safeB}/chapters/${safeC}.md`;
  const txt = $("#btn-exp-txt"); if (txt) txt.href = `${API_BASE_URL}/books/${safeB}/chapters/${safeC}.txt`;
  const pdf = $("#btn-exp-pdf"); if (pdf) pdf.href = `${API_BASE_URL}/books/${safeB}/chapters/${safeC}.pdf`;
}

async function refreshChapterList(bookId){
  // prendiamo i capitoli dal /books e filtriamo
  try{
    const res = await fetch(`${API_BASE_URL}/books?ts=${Date.now()}`, {cache:"no-store"});
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const items = await res.json();
    const book = items.find(b => (b.id === bookId));
    const list = $("#chapters-list");
    showChaptersPanel(true);
    if (!book || !Array.isArray(book.chapters) || book.chapters.length===0){
      if(list) list.innerHTML = `<div class="muted">Nessun capitolo ancora.</div>`;
      return;
    }
    // render
    const ul = document.createElement("div");
    book.chapters.sort((a,b)=> (a.id||"").localeCompare(b.id||""));
    book.chapters.forEach(ch=>{
      const row = document.createElement("div");
      row.className = "row";
      row.style = "display:flex;align-items:center;justify-content:space-between;border-top:1px solid #22324a;padding:10px 0;";
      const meta = document.createElement("div");
      meta.innerHTML = `<div><strong>${escapeHtml(ch.id || "")}</strong></div>
                        <div class="muted">ID: ${escapeHtml(ch.id || "")} · ${escapeHtml(ch.updated_at || "")}</div>`;
      const actions = document.createElement("div");
      actions.className = "row-right";
      actions.innerHTML = `
        <button class="btn btn-secondary" data-ch-open="${escapeAttr(ch.id)}">Apri</button>
        <button class="btn btn-ghost" data-ch-del="${escapeAttr(ch.id)}">Elimina</button>
        <a class="btn btn-ghost" target="_blank" href="${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(ch.id)}.md">MD</a>
        <a class="btn btn-ghost" target="_blank" href="${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(ch.id)}.txt">TXT</a>
        <a class="btn btn-ghost" target="_blank" href="${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(ch.id)}.pdf">PDF</a>
      `;
      row.appendChild(meta);
      row.appendChild(actions);
      ul.appendChild(row);
    });
    if(list) list.innerHTML = "", list.appendChild(ul);

    // wiring azioni inline
    $("#chapters-list").onclick = async (ev)=>{
      const openBtn = ev.target.closest("[data-ch-open]");
      const delBtn  = ev.target.closest("[data-ch-del]");
      if(openBtn){
        const chId = openBtn.getAttribute("data-ch-open");
        await loadChapter(bookId, chId);
      }else if(delBtn){
        const chId = delBtn.getAttribute("data-ch-del");
        if(confirm("Eliminare il capitolo?")){
          const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chId)}`, {method:"DELETE"});
          if(!res.ok && res.status !== 204) return toast("Errore nell'eliminazione.");
          await refreshChapterList(bookId);
        }
      }
    };
  }catch(e){
    console.error(e);
    const list = $("#chapters-list");
    if(list) list.innerHTML = `<div class="error">Errore capitoli: ${e.message || e}</div>`;
  }
}

async function loadChapter(bookId, chapterId){
  try{
    const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}?ts=${Date.now()}`, {cache:"no-store"});
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    $("#bookIdInput").value = bookId;
    $("#chapterIdInput").value = chapterId;
    $("#chapterText").value = data?.content || "";
    setExportLinks(bookId, chapterId);
    showEditor(true);
  }catch(e){
    toast("Impossibile caricare il capitolo: " + (e.message || e));
  }
}

async function saveChapter(){
  const bookId = $("#bookIdInput").value.trim();
  const chId   = $("#chapterIdInput").value.trim();
  const text   = $("#chapterText").value;
  if(!bookId || !chId) return toast("Compila Book ID e Chapter ID.");
  try{
    const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chId)}`, {
      method:"PUT",
      headers:{"Content-Type":"application/json"},
      body: JSON.stringify({content:text || ""})
    });
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    setExportLinks(bookId, chId);
    await refreshChapterList(bookId);
    toast("💾 Capitolo salvato.");
  }catch(e){
    toast("Errore salvataggio: " + (e.message || e));
  }
}

/* Azioni */
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
    alert("✅ Libro creato!");
    await toggleLibrary(true);
    await fetchBooks();
    setTimeout(fetchBooks, 400);
  } catch (e) {
    alert("Errore di rete: " + (e?.message || e));
  }
}

async function deleteBook(bookId) {
  if (!bookId) return;
  const ok = confirm("Eliminare questo libro?");
  if (!ok) return;
  try {
    const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}`, { method: "DELETE" });
    if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
    toast("Libro eliminato.");
    await fetchBooks();
  } catch (e) {
    toast("Errore: " + (e?.message || e));
  }
}

function goEditor(bookId) {
  showEditor(true);
  const id = bookId || loadLastBook() || "";
  if ($("#bookIdInput")) $("#bookIdInput").value = id;
  if ($("#chapterIdInput") && !$("#chapterIdInput").value) $("#chapterIdInput").value = "ch_0001";
  if ($("#chapterText") && !$("#chapterText").value) $("#chapterText").value = "Scrivi qui il contenuto del capitolo…";
  if (id) refreshChapterList(id);
  setExportLinks(id, $("#chapterIdInput").value || "ch_0001");
}

function closeEditor(){ showEditor(false); }

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

/* AI */
async function writeWithAI(){
  const bookId = $("#bookIdInput").value.trim();
  const chId   = $("#chapterIdInput").value.trim() || "ch_0001";
  const topic  = $("#chapterTopicInput").value.trim() || "Capitolo";
  if(!bookId) return toast("Inserisci un Book ID.");
  try{
    const res = await fetch(`${API_BASE_URL}/generate/chapter`, {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify({ book_id: bookId, chapter_id: chId, topic })
    });
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    $("#chapterText").value = data?.content || "";
  }catch(e){
    toast("AI non disponibile: " + (e.message || e));
  }
}

/* Wiring */
function wireButtons() {
  // Topbar
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", () => toggleLibrary());
  $("#btn-editor")?.addEventListener("click", () => goEditor());

  // Azioni rapide (toggle richiesto)
  $("#btn-quick-create")?.addEventListener("click", createBookSimple);
  $("#btn-quick-library")?.addEventListener("click", () => toggleLibrary());
  $("#btn-quick-editor")?.addEventListener("click", () => goEditor());

  // Editor
  $("#btn-ed-close")?.addEventListener("click", closeEditor);
  $("#btn-ed-save")?.addEventListener("click", saveChapter);
  $("#btn-ai")?.addEventListener("click", writeWithAI);
  $("#btn-ed-del")?.addEventListener("click", async ()=>{
    const bookId = $("#bookIdInput").value.trim();
    const chId   = $("#chapterIdInput").value.trim();
    if(!bookId || !chId) return toast("Compila Book ID e Chapter ID.");
    if(!confirm("Eliminare questo capitolo?")) return;
    const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chId)}`, {method:"DELETE"});
    if(!res.ok && res.status !== 204) return toast("Errore nell'eliminazione.");
    $("#chapterText").value = "";
    await refreshChapterList(bookId);
  });

  // Deleghe Libreria
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

/* Init */
document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();
  await toggleLibrary(true);
});
