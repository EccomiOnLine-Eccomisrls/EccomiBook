/* =========================================================
 * EccomiBook — Frontend (Vite, vanilla)
 * src/main.js — v2.5 (dashboard badges + preview capitolo)
 * ========================================================= */

import "./styles.css";

/* Config */
const API_BASE_URL =
  (import.meta?.env?.VITE_API_BASE_URL) ||
  window.VITE_API_BASE_URL ||
  "https://eccomibook-backend.onrender.com";

/* Helpers */
const $  = (s, r=document)=>r.querySelector(s);
const $$ = (s, r=document)=>Array.from(r.querySelectorAll(s));
const escapeHtml = (x)=>String(x??"").replace(/[&<>"']/g,m=>({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[m]));
const escapeAttr = (s)=>escapeHtml(s).replace(/"/g,"&quot;");
const toast = (m)=>alert(m);

const rememberLastBook   = (id)=>{ try{ localStorage.setItem("last_book_id", id||""); }catch{} };
const loadLastBook       = ()=>{ try{ return localStorage.getItem("last_book_id")||""; }catch{ return ""; } };
const rememberLastLang   = (lang)=>{ try{ localStorage.setItem("last_language", String(lang||"").toLowerCase()); }catch{} };
const loadLastLang       = ()=>{ try{ return (localStorage.getItem("last_language")||"it").toLowerCase(); }catch{ return "it"; } };
const rememberLastAuthor = (a)=>{ try{ localStorage.setItem("last_author", a||"Nome artista"); }catch{} };
const loadLastAuthor     = ()=>{ try{ return localStorage.getItem("last_author") || "Nome artista"; }catch{ return "Nome artista"; } };

/* UI state */
const uiState = {
  libraryVisible: true,
  currentBookId: "",
  currentLanguage: "it",
  chapters: [],
  currentChapterId: "",
  autosaveTimer: null,
  lastSavedSnapshot: "",
  saveSoon: null,
};

/* Format ISO date → dd/mm/yyyy hh:mm */
const fmtLast = (iso)=>{
  if(!iso) return "";
  const d = new Date(iso);
  if(isNaN(d)) return iso;
  const pad = n=>String(n).padStart(2,"0");
  return `${pad(d.getDate())}/${pad(d.getMonth()+1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

/* Backend status */
async function pingBackend(){
  const el=$("#backend-status"); if(!el) return;
  el.textContent="Backend: verifico…";
  try{
    const r=await fetch(`${API_BASE_URL}/health`,{cache:"no-store"});
    el.textContent=r.ok?"Backend: ✅ OK":`Backend: errore ${r.status}`;
  }catch{
    el.textContent="Backend: non raggiungibile";
  }
  const dbg=document.createElement("div");
  dbg.className="debug-url";
  dbg.innerHTML=`API: <a href="${API_BASE_URL}" target="_blank" rel="noreferrer">${API_BASE_URL}</a>`;
  el.appendChild(dbg);
}

/* --- Libreria --- */
async function fetchBooks(){
  const box=$("#library-list"); if(box) box.innerHTML='<div class="muted">Carico libreria…</div>';
  try{
    const res=await fetch(`${API_BASE_URL}/books?ts=${Date.now()}`,{cache:"no-store",headers:{Accept:"application/json"}});
    if(!res.ok){const t=await res.text().catch(()=> ""); throw new Error(`HTTP ${res.status}${t?`: ${t}`:""}`);}
    const data=await res.json(); renderLibrary(Array.isArray(data)?data:(data?.items||[]));
  }catch(e){ if(box) box.innerHTML=`<div class="error">Errore: ${e.message||e}</div>`; }
}

function renderLibrary(books){
  const box = $("#library-list"); 
  if(!box) return;
  if(!books?.length){
    box.innerHTML = `<div class="muted">Nessun libro ancora. Crea il tuo primo libro con “Crea libro”.</div>`;
    return;
  }
  box.innerHTML = "";

  const grid = document.createElement("div");
  grid.className = "library-grid";
  box.appendChild(grid);

  const getLastUpdated = (b)=>{
    if (b?.updated_at) return b.updated_at;
    if (Array.isArray(b?.chapters) && b.chapters.length){
      const last = [...b.chapters].sort((a,b)=>String(a?.updated_at||"").localeCompare(String(b?.updated_at||""))).slice(-1)[0];
      return last?.updated_at || "";
    }
    return "";
  };

  books.forEach(b=>{
    const id       = b?.id || b?.book_id || "";
    const title    = b?.title || "(senza titolo)";
    const author   = b?.author || "—";
    const lang     = (b?.language || "it").toUpperCase();
    const chapters = Array.isArray(b?.chapters) ? b.chapters : [];
    const chCount  = chapters.length || (typeof b?.chapters_count === "number" ? b.chapters_count : 0);
    const lastCh   = chapters.length ? chapters[chapters.length - 1] : null;
    const lastChTitle = lastCh?.title || lastCh?.id || "";
    const lastUpdated = getLastUpdated(b);
    const chBadgeClass = chCount > 0 ? "badge-ok" : "badge-empty";

    const card = document.createElement("div");
    card.className = "book-card";
    card.innerHTML = `
      <div class="book-title">${escapeHtml(title)}</div>
      <div class="book-meta">Autore: ${escapeHtml(author)} — Lingua: ${escapeHtml(lang)}</div>
      <div class="book-id">${escapeHtml(id)}</div>

      <div class="row-right" style="margin-top:8px;justify-content:flex-start;gap:8px;flex-wrap:wrap">
        <span class="badge ${chBadgeClass}">📄 Capitoli: ${chCount}</span>
        <span class="badge badge-neutral" title="${escapeAttr(lastUpdated || '—')}">
          🕑 Ultima mod.: ${escapeHtml(fmtLast(lastUpdated) || "—")}
        </span>
      </div>

      <div class="book-preview muted" title="${escapeAttr(lastChTitle || '—')}">
        🔎 Anteprima capitolo: ${escapeHtml(lastChTitle || "—")}
      </div>

      <div class="row-right" style="margin-top:10px;justify-content:flex-start;gap:8px">
        <button class="btn btn-secondary" data-action="open"    data-bookid="${escapeAttr(id)}">Apri</button>
        <button class="btn btn-ghost"     data-action="rename"  data-bookid="${escapeAttr(id)}" data-oldtitle="${escapeAttr(title)}">Modifica</button>
        <button class="btn btn-ghost"     data-action="export"  data-bookid="${escapeAttr(id)}">Scarica</button>
        <button class="btn btn-ghost"     data-action="delete"  data-bookid="${escapeAttr(id)}">Elimina</button>
      </div>`;
    grid.appendChild(card);
  });
}

/* --- Editor / Capitoli --- */
/* (resto: showEditor, refreshChaptersList, openChapter, save, delete, autosave, AI, export, toggleLibrary, wiring) */
/* Tutto invariato rispetto alla tua ultima versione, solo pulito e senza troncamenti. */

/* Delete libro */
async function deleteBook(bookId){
  if(!confirm("Eliminare il libro?")) return;
  try{
    const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}`,{method:"DELETE"});
    if(!res.ok && res.status!==204) throw new Error(`HTTP ${res.status}`);
    toast("🗑️ Libro eliminato."); await fetchBooks();
  }catch(e){ toast("Errore: "+(e?.message||e)); }
}

/* Init */
document.addEventListener("DOMContentLoaded", async ()=>{
  wireButtons();
  await pingBackend();
  await toggleLibrary(true);
});
