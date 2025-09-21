/* =========================================================
 * EccomiBook — Frontend (Vite, vanilla)
 * src/main.js — COMPLETO
 * ========================================================= */
import "./styles.css";

const API_BASE_URL =
  (import.meta?.env?.VITE_API_BASE_URL) ||
  window.VITE_API_BASE_URL ||
  "https://eccomibook-backend.onrender.com";

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function toast(msg){ alert(msg); }
function rememberLastBook(id){ try{localStorage.setItem("last_book_id", id||"");}catch{} }
function loadLastBook(){ try{return localStorage.getItem("last_book_id")||"";}catch{return"";} }
function escapeHtml(s){ return String(s??"").replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])); }
function escapeAttr(s){ return escapeHtml(s).replace(/"/g,"&quot;"); }

const uiState = { libraryVisible:true, currentBookId:"", currentChapterId:"" };

/* ------------ Backend ping ------------ */
async function pingBackend(){
  const el = $("#backend-status"); if(!el) return;
  el.textContent = "Backend: verifico…";
  try{
    const r = await fetch(`${API_BASE_URL}/health`, {cache:"no-store"});
    el.textContent = r.ok ? "Backend: ✅ OK" : `Backend: errore ${r.status}`;
  }catch{ el.textContent = "Backend: non raggiungibile"; }
  const dbg = document.createElement("div");
  dbg.className = "debug-url";
  dbg.innerHTML = `API: <a href="${API_BASE_URL}" target="_blank" rel="noreferrer">${API_BASE_URL}</a>`;
  el.appendChild(dbg);
}

/* ------------ Libreria ------------ */
async function fetchBooks(){
  const box = $("#library-list"); if(box) box.innerHTML = '<div class="muted">Carico libreria…</div>';
  try{
    const res = await fetch(`${API_BASE_URL}/books?ts=${Date.now()}`, {cache:"no-store", headers:{"Accept":"application/json"}});
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const items = Array.isArray(data)? data : (data?.items||[]);
    renderLibrary(items);
  }catch(e){
    if(box) box.innerHTML = `<div class="error">Errore: ${e.message||e}</div>`;
  }
}
function renderLibrary(books){
  const box = $("#library-list"); if(!box) return;
  if(!books || !books.length){ box.innerHTML = `<div class="muted">Nessun libro ancora. Crea il tuo primo libro con “Crea libro”.</div>`; return; }
  box.innerHTML = "";
  const grid = document.createElement("div"); grid.className = "library-grid"; box.appendChild(grid);
  books.forEach(b=>{
    const id = b?.id || b?.book_id || ""; const title=b?.title||"(senza titolo)"; const author=b?.author||"—"; const lang=b?.language||"it";
    const card = document.createElement("div"); card.className="book-card";
    card.innerHTML = `
      <div class="book-title">${escapeHtml(title)}</div>
      <div class="book-meta">Autore: ${escapeHtml(author)} — Lingua: ${escapeHtml(lang)}</div>
      <div class="book-id">${escapeHtml(id)}</div>
      <div class="row-right" style="margin-top:10px">
        <button class="btn btn-secondary" data-action="open" data-bookid="${escapeAttr(id)}">Apri</button>
        <button class="btn btn-ghost" data-action="edit" data-bookid="${escapeAttr(id)}">Modifica</button>
        <button class="btn btn-ghost" data-action="delete" data-bookid="${escapeAttr(id)}">Elimina</button>
      </div>`;
    grid.appendChild(card);
  });
}

/* ------------ Libro + Capitoli ------------ */
async function fetchBook(bookId){
  const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}?ts=${Date.now()}`, {cache:"no-store"});
  if(!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

function renderChaptersList(book){
  const panel = $("#chapters-panel"); if(!panel) return;
  const list = $("#chapters-list"); if(!list) return;

  const chapters = book?.chapters || [];
  if(!chapters.length){ list.innerHTML = `<div class="muted">Nessun capitolo ancora.</div>`; return; }

  list.innerHTML = "";
  chapters.forEach(ch=>{
    const row = document.createElement("div");
    row.className = "card";
    row.style.margin="8px 0";
    const id = ch.id;
    row.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div>
          <strong>${escapeHtml(id)}</strong>
          <div class="muted">ID: ${escapeHtml(id)} · ${escapeHtml(ch.updated_at||"")}</div>
        </div>
        <div class="row-right">
          <button class="btn btn-secondary" data-ch-open="${escapeAttr(id)}">Apri</button>
          <button class="btn btn-ghost" data-ch-del="${escapeAttr(id)}">Elimina</button>
          <a class="btn btn-ghost" href="${API_BASE_URL}/books/${encodeURIComponent(book.id)}/chapters/${encodeURIComponent(id)}.md" target="_blank" rel="noreferrer">MD</a>
          <a class="btn btn-ghost" href="${API_BASE_URL}/books/${encodeURIComponent(book.id)}/chapters/${encodeURIComponent(id)}.txt" target="_blank" rel="noreferrer">TXT</a>
          <a class="btn btn-ghost" href="${API_BASE_URL}/books/${encodeURIComponent(book.id)}/chapters/${encodeURIComponent(id)}.pdf" target="_blank" rel="noreferrer">PDF</a>
        </div>
      </div>`;
    list.appendChild(row);
  });
  panel.style.display = "block";
}

async function refreshChapterList(bookId){
  try{
    const book = await fetchBook(bookId);
    renderChaptersList(book);
  }catch(e){ console.warn("refreshChapterList", e); }
}

async function openBookInEditor(bookId){
  uiState.currentBookId = bookId;
  rememberLastBook(bookId);

  // mostra editor
  const ed = $("#editor-card"); if(ed) ed.style.display = "block";
  $("#bookIdInput").value = bookId;
  if(!$("#chapterIdInput").value) $("#chapterIdInput").value = "ch_0001";
  const ta = $("#chapterText");
  if(ta && !ta.value) ta.value = "Scrivi qui il contenuto del capitolo…";

  await refreshChapterList(bookId);
}

async function loadChapter(bookId, chapterId){
  try{
    const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}?ts=${Date.now()}`, {cache:"no-store"});
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    $("#chapterIdInput").value = chapterId;
    $("#chapterText").value = data?.content || "";
    uiState.currentChapterId = chapterId;
  }catch(e){
    toast("Capitolo non trovato o vuoto."); console.warn(e);
  }
}

async function saveChapter(){
  const bookId = $("#bookIdInput").value.trim();
  const chapterId = $("#chapterIdInput").value.trim();
  const content = $("#chapterText").value;

  if(!bookId || !chapterId){ toast("Book ID e Chapter ID sono obbligatori."); return; }

  const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`, {
    method: "PUT",
    headers: {"Content-Type":"application/json"},
    cache: "no-store",
    body: JSON.stringify({ content })
  });
  if(!res.ok){
    const t = await res.text().catch(()=> "");
    toast(`Errore salvataggio: HTTP ${res.status} ${t}`); return;
  }
  toast("💾 Salvato.");
  await refreshChapterList(bookId);
}

/* ------------ Azioni rapide / libreria ------------ */
async function createBookSimple(){
  const title = prompt("Titolo del libro:", "Manuale EccomiBook");
  if(title == null) return;
  try{
    const res = await fetch(`${API_BASE_URL}/books/create`, {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      cache:"no-store",
      body: JSON.stringify({ title: title.trim()||"Senza titolo", author:"EccomiBook", language:"it", chapters:[] })
    });
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const newId = data?.book_id || data?.id || "";
    rememberLastBook(newId);
    alert("✅ Libro creato!");
    await toggleLibrary(true);
    await fetchBooks();
    setTimeout(fetchBooks, 400);
  }catch(e){ alert("Errore di rete: " + (e?.message||e)); }
}

async function deleteBook(bookId){
  if(!bookId) return;
  if(!confirm("Eliminare questo libro?")) return;
  const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}`, {method:"DELETE"});
  if(!res.ok && res.status !== 204){
    const t = await res.text().catch(()=> "");
    toast(`Errore: HTTP ${res.status} ${t}`); return;
  }
  toast("Libro eliminato."); await fetchBooks();
}

/* ------------ Toggle Libreria ------------ */
async function toggleLibrary(force){
  const lib = $("#library-section"); if(!lib) return;
  if(typeof force === "boolean") uiState.libraryVisible = force;
  else uiState.libraryVisible = !uiState.libraryVisible;
  lib.style.display = uiState.libraryVisible ? "block" : "none";
  if(uiState.libraryVisible) await fetchBooks();
}

/* ------------ Wiring ------------ */
function wireButtons(){
  // Topbar
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", ()=> toggleLibrary());
  $("#btn-editor")?.addEventListener("click", ()=> openBookInEditor(loadLastBook()));

  // Azioni rapide
  $("#btn-quick-create")?.addEventListener("click", createBookSimple);
  $("#btn-quick-library")?.addEventListener("click", ()=> toggleLibrary()); // toggle come richiesto
  $("#btn-quick-editor")?.addEventListener("click", ()=> openBookInEditor(loadLastBook()));

  // Editor
  $("#btn-ed-close")?.addEventListener("click", ()=>{ $("#editor-card").style.display="none"; });
  $("#btn-ed-save")?.addEventListener("click", saveChapter);

  // Lista libreria: delega
  $("#library-list")?.addEventListener("click", async (ev)=>{
    const btn = ev.target.closest("button[data-action]"); if(!btn) return;
    const action = btn.getAttribute("data-action");
    const bookId = btn.getAttribute("data-bookid") || "";
    if(action === "open"){ await openBookInEditor(bookId); }
    else if(action === "delete"){ await deleteBook(bookId); }
    else if(action === "edit"){ toast("✏️ Modifica libro: in arrivo."); }
  });

  // Lista capitoli: delega
  $("#chapters-list")?.addEventListener("click", async (ev)=>{
    const t = ev.target;
    const openId = t.getAttribute?.("data-ch-open");
    const delId  = t.getAttribute?.("data-ch-del");
    const bookId = uiState.currentBookId;
    if(openId){ await loadChapter(bookId, openId); }
    else if(delId){
      if(!confirm("Eliminare questo capitolo?")) return;
      const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(delId)}`, {method:"DELETE"});
      if(!res.ok && res.status !== 204){ toast("Errore nell'eliminazione."); return; }
      await refreshChapterList(bookId);
      if($("#chapterIdInput").value === delId){ $("#chapterText").value = ""; }
    }
  });

  // AI (MVP)
  $("#btn-ai")?.addEventListener("click", async ()=>{
    const bookId = $("#bookIdInput").value.trim();
    const chapterId = $("#chapterIdInput").value.trim();
    const topic = ($("#chapterTopicInput")?.value || "").trim();
    if(!bookId || !chapterId){ toast("Compila Book ID e Chapter ID."); return; }
    try{
      const res = await fetch(`${API_BASE_URL}/generate/chapter`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ book_id: bookId, chapter_id: chapterId, topic: topic || "Capitolo" })
      });
      if(!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      $("#chapterText").value = data?.content || "(nessun contenuto generato)";
    }catch(e){ toast("Errore AI: " + (e?.message||e)); }
  });
}

/* ------------ Init ------------ */
document.addEventListener("DOMContentLoaded", async ()=>{
  wireButtons();
  await pingBackend();
  await toggleLibrary(true); // mostra e carica libreria
});
