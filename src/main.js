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

const rememberLastBook = (id)=>{ try{ localStorage.setItem("last_book_id", id||""); }catch{} };
const loadLastBook      = ()=>{ try{ return localStorage.getItem("last_book_id")||""; }catch{ return ""; } };

const rememberLastLang = (lang)=>{ try{ localStorage.setItem("last_language", String(lang||"").toLowerCase()); }catch{} };
const loadLastLang     = ()=>{ try{ return (localStorage.getItem("last_language")||"it").toLowerCase(); }catch{ return "it"; } };

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

/* Formatta ISO → dd/mm/yyyy hh:mm */
const fmtLast = (iso)=>{
  if(!iso) return "";
  const d = new Date(iso);
  if(isNaN(d)) return iso;
  const pad = n=>String(n).padStart(2,"0");
  return `${pad(d.getDate())}/${pad(d.getMonth()+1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

/* Ping backend */
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

/* Libreria */
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
      <div class="book-meta">
        Autore: ${escapeHtml(author)} — Lingua: ${escapeHtml(lang)}
      </div>
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

/* Editor / Capitoli */
async function showEditor(bookId){
  uiState.currentBookId = bookId || loadLastBook() || ""; if(!uiState.currentBookId) return;
  rememberLastBook(uiState.currentBookId);
  $("#editor-card").style.display="block";
  $("#bookIdInput").value=uiState.currentBookId;

  const ch=$("#chapterIdInput"); if(!ch.value) ch.value="ch_0001";
  const ta=$("#chapterText"); if(!ta.value) ta.value="Scrivi qui il contenuto del capitolo…";
  uiState.currentChapterId=ch.value.trim(); uiState.lastSavedSnapshot=ta.value;

  await loadBookLanguage(uiState.currentBookId);
  refreshChaptersList(uiState.currentBookId).then(()=>{
    if(uiState.chapters.some(c=>c.id===uiState.currentChapterId)) openChapter(uiState.currentBookId, uiState.currentChapterId);
  });
  startAutosave();
}
function closeEditor(){ stopAutosave(); $("#editor-card").style.display="none"; }

/* lingua libro corrente */
async function loadBookLanguage(bookId){
  try{
    const r=await fetch(`${API_BASE_URL}/books?ts=${Date.now()}`,{cache:"no-store"}); if(!r.ok) return;
    const arr=(await r.json()); const items=Array.isArray(arr)?arr:(arr?.items||[]);
    const bk=items.find(b=>(b?.id||b?.book_id)===bookId);
    uiState.currentLanguage=String(bk?.language||loadLastLang()||"it").toLowerCase();
  }catch{
    uiState.currentLanguage=loadLastLang()||"it";
  }
  const langInput=$("#languageInput");
  if(langInput){ langInput.value=uiState.currentLanguage; }
  rememberLastLang(uiState.currentLanguage);
}

/* elenco capitoli */
async function refreshChaptersList(bookId){
  const list=$("#chapters-list"); if(list) list.innerHTML='<div class="muted">Carico capitoli…</div>';
  try{
    const r=await fetch(`${API_BASE_URL}/books?ts=${Date.now()}`,{cache:"no-store"});
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    const all=await r.json(); const arr=Array.isArray(all)?all:(all?.items||[]);
    const found=arr.find(x=>(x?.id||x?.book_id)===bookId);
    const chapters=found?.chapters||[];
    uiState.chapters=chapters.map(c=>({id:c?.id||"",title:c?.title||c?.id||"",updated_at:c?.updated_at||"",path:c?.path||""}));
    renderChaptersList(bookId, uiState.chapters);
  }catch(e){ if(list) list.innerHTML=`<div class="error">Errore: ${e.message||e}</div>`; }
}
function renderChaptersList(bookId, chapters){
  const list=$("#chapters-list"); if(!list) return;
  if(!chapters?.length){ list.innerHTML=`<div class="muted">Nessun capitolo ancora.</div>`; return; }
  list.innerHTML="";
  const nav=document.createElement("div");
  nav.className="row-right"; nav.style.justifyContent="flex-start"; nav.style.marginBottom="8px";
  nav.innerHTML=`<button class="btn btn-ghost" id="btn-ch-prev">← Precedente</button>
                 <button class="btn btn-ghost" id="btn-ch-next">Successivo →</button>`;
  list.appendChild(nav);

  chapters.forEach(ch=>{
    const cid=ch.id, updated=ch.updated_at||"";
    const li=document.createElement("div"); li.className="card chapter-row"; li.style.margin="8px 0";
    li.innerHTML=`
      <div class="chapter-head">
        <div>
          <div style="font-weight:600">${escapeHtml(ch.title||cid)}</div>
          <div class="muted">ID: ${escapeHtml(cid)}${updated?` · ${escapeHtml(updated)}`:""}</div>
        </div>
      </div>
      <div class="chapter-actions">
        <button class="btn btn-secondary" data-ch-open="${escapeAttr(cid)}">Apri</button>
        <button class="btn btn-ghost" data-ch-edit="${escapeAttr(cid)}">Modifica</button>
        <button class="btn btn-ghost" data-ch-del="${escapeAttr(cid)}">Elimina</button>
        <button class="btn btn-ghost" data-ch-dl="${escapeAttr(cid)}">Scarica</button>
      </div>`;
    list.appendChild(li);
  });

  $("#btn-ch-prev")?.addEventListener("click",()=>stepChapter(-1));
  $("#btn-ch-next")?.addEventListener("click",()=>stepChapter(+1));
}
const chapterIndex=(cid)=>uiState.chapters.findIndex(c=>c.id===cid);
function stepChapter(delta){
  if(!uiState.chapters.length) return;
  const idx=chapterIndex(uiState.currentChapterId);
  const next=Math.min(Math.max(idx+delta,0),uiState.chapters.length-1);
  const target=uiState.chapters[next]?.id;
  if(target && target!==uiState.currentChapterId) maybeAutosaveNow().finally(()=>openChapter(uiState.currentBookId,target));
}
async function openChapter(bookId, chapterId){
  try{
    const r=await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}?ts=${Date.now()}`,{cache:"no-store"});
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    const data=await r.json();
    $("#bookIdInput").value=bookId; $("#chapterIdInput").value=chapterId; $("#chapterText").value=data?.content||"";
    uiState.currentBookId=bookId; uiState.currentChapterId=chapterId; uiState.lastSavedSnapshot=$("#chapterText").value;
    toast(`📖 Aperto ${chapterId}`);
  }catch(e){ toast("Impossibile aprire il capitolo: "+(e?.message||e)); }
}
async function deleteChapter(bookId, chapterId){
  if(!confirm(`Eliminare il capitolo ${chapterId}?`)) return;
  try{
    const r=await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`,{method:"DELETE"});
    if(!r.ok && r.status!==204) throw new Error(`HTTP ${r.status}`);
    toast("🗑️ Capitolo eliminato."); await refreshChaptersList(bookId);
    if(uiState.currentChapterId===chapterId){ $("#chapterText").value=""; uiState.currentChapterId=""; }
  }catch(e){ toast("Errore eliminazione: "+(e?.message||e)); }
}
function editChapter(cid){ $("#chapterIdInput").value=cid; uiState.currentChapterId=cid; openChapter(uiState.currentBookId,cid).then(()=>$("#chapterText")?.focus()); }
async function saveCurrentChapter(showToast=true){
  const bookId=$("#bookIdInput").value.trim(), chapterId=$("#chapterIdInput").value.trim(), content=$("#chapterText").value;
  if(!bookId || !chapterId) return toast("Inserisci Book ID e Chapter ID.");
  try{
    const r=await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`,{
      method:"PUT", headers:{ "Content-Type":"application/json" }, body:JSON.stringify({ content })
    });
    if(!r.ok){ const t=await r.text().catch(()=> ""); throw new Error(`HTTP ${r.status}${t?`: ${t}`:""}`); }
    uiState.lastSavedSnapshot=content; if(showToast) toast("✅ Capitolo salvato."); refreshChaptersList(bookId);
  }catch(e){ toast("Errore salvataggio: "+(e?.message||e)); }
}

/* Autosave */
function startAutosave(){ stopAutosave(); uiState.autosaveTimer=setInterval(maybeAutosaveNow,30_000); }
function stopAutosave(){ if(uiState.autosaveTimer) clearInterval(uiState.autosaveTimer); uiState.autosaveTimer=null; }
async function maybeAutosaveNow(){
  const txt=$("#chapterText")?.value ?? "";
  if(txt!==uiState.lastSavedSnapshot && uiState.currentBookId && uiState.currentChapterId) await saveCurrentChapter(false);
}

/* AI (usa lingua del campo o del libro) */
async function generateWithAI(){
  const bookId   = $("#bookIdInput").value.trim()||uiState.currentBookId;
  const chapterId= $("#chapterIdInput").value.trim();
  const topic    = $("#topicInput")?.value?.trim()||"";
  const language = ($("#languageInput")?.value?.trim().toLowerCase()||uiState.currentLanguage||"it");
  if(!bookId || !chapterId) return toast("Inserisci Book ID e Chapter ID.");

  uiState.currentLanguage = language;
  rememberLastLang(language);

  try{
    const r=await fetch(`${API_BASE_URL}/generate/chapter`,{
      method:"POST", headers:{ "Content-Type":"application/json" },
      body:JSON.stringify({ book_id:bookId, chapter_id:chapterId, topic, language })
    });
    if(!r.ok){ const t=await r.text().catch(()=> ""); throw new Error(`HTTP ${r.status}${t?`: ${t}`:""}`); }
    const data=await r.json(); $("#chapterText").value=data?.content||data?.text||"";
    toast(`✨ Testo generato (bozza) — lingua: ${language.toUpperCase()}`);
    await saveCurrentChapter(false); await refreshChaptersList(bookId);
  }catch(e){ toast("⚠️ AI di test: "+(e?.message||e)); }
}

/* Export */
function askFormat(defaultFmt="pdf"){
  const a=prompt("Formato? (pdf / md / txt)",defaultFmt)?.trim().toLowerCase();
  if(!a) return null; if(!["pdf","md","txt"].includes(a)){ toast("Formato non valido."); return null; } return a;
}
function downloadChapter(bookId, chapterId){
  const fmt=askFormat("pdf"); if(!fmt) return;
  window.open(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}/${fmt}`,"_blank","noopener");
}
async function exportBook(bookId){
  const fmt=askFormat("pdf"); if(!fmt) return;
  if(fmt==="pdf"){
    try{
      const r=await fetch(`${API_BASE_URL}/generate/export/book/${encodeURIComponent(bookId)}`,{method:"POST",headers:{ "Content-Type":"application/json" }});
      if(!r.ok) throw new Error(`HTTP ${r.status}`);
      const data=await r.json(); const url=data?.download_url||data?.url;
      return url?window.open(url,"_blank","noopener"):toast
