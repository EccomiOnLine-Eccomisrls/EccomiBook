/* =========================================================
 * EccomiBook — Frontend
 * src/main.js — v3.8
 * - LED stato backend
 * - Libreria + Editor
 * - Dropdown custom per pulsanti verdi (Book/Chapter)
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

/* Local storage */
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
  currentBookTitle: "",
  currentLanguage: "it",
  books: [],
  chapters: [],
  currentChapterId: "",
  autosaveTimer: null,
  lastSavedSnapshot: "",
  saveSoon: null,
  openMenuEl: null,
};

/* Date utils */
const fmtLast = (iso)=>{
  if(!iso) return "";
  const d = new Date(iso);
  if(isNaN(d)) return iso;
  const pad = n=>String(n).padStart(2,"0");
  return `${pad(d.getDate())}/${pad(d.getMonth()+1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};
const fmtHHMM = (d=new Date())=>{
  const pad=n=>String(n).padStart(2,"0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

/* HERO helpers */
function syncEditorButtonState(){
  const editorBtn = $("#btn-editor"); if(!editorBtn) return;
  const hasBook = !!(loadLastBook());
  editorBtn.disabled = !hasBook;
  editorBtn.title = hasBook ? "Scrivi e salva capitoli" : "Apri un libro dalla Libreria";
  editorBtn.classList.toggle("is-disabled", !hasBook);
}

/* ======== Status LED ======== */
function renderStatus({mode,title,sub}){
  const el=$("#backend-status"); if(!el) return;
  const ledClass = mode==="ok" ? "led--ok" : mode==="warn" ? "led--warn" : "led--ko";
  el.innerHTML = `
    <div class="statusbox" role="status" aria-live="polite">
      <span class="statusbox__led ${ledClass}" aria-hidden="true"></span>
      <div class="statusbox__text">
        <span class="statusbox__title">${escapeHtml(title)}</span>
        <span class="statusbox__sub">${escapeHtml(sub)}</span>
      </div>
    </div>`;
}
async function pingBackend(){
  renderStatus({mode:"warn", title:"EccomiBook Live", sub:"Verifica in corso..."});
  try{
    const r=await fetch(`${API_BASE_URL}/health`,{cache:"no-store"});
    renderStatus(r.ok
      ? {mode:"ok", title:"EccomiBook Live", sub:`Ultimo aggiornamento: ${fmtHHMM()}`}
      : {mode:"ko", title:"EccomiBook Offline", sub:`Errore ${r.status}`});
  }catch{
    renderStatus({mode:"ko", title:"EccomiBook Offline", sub:"Servizio non raggiungibile"});
  }
}

/* ======== Menu popup custom (per pulsanti verdi) ======== */
function closeMenu(){
  uiState.openMenuEl?.remove();
  uiState.openMenuEl = null;
  document.removeEventListener("click", onDocClick);
  window.removeEventListener("resize", closeMenu);
  window.removeEventListener("scroll", closeMenu, true);
}
function onDocClick(e){
  if (uiState.openMenuEl && !uiState.openMenuEl.contains(e.target)) closeMenu();
}
function showMenuForButton(btn, items, onPick){
  closeMenu();
  const rect = btn.getBoundingClientRect();
  const host = document.createElement("div");
  host.className = "menu-pop";
  host.style.left = `${Math.max(10, rect.left + window.scrollX)}px`;
  host.style.top  = `${rect.bottom + window.scrollY + 6}px`;

  if(!items.length){
    host.innerHTML = `<div class="muted" style="padding:6px 8px">Nessun elemento</div>`;
  }else{
    host.innerHTML = items.map(x =>
      `<button type="button" data-val="${escapeAttr(x.value)}">
         ${escapeHtml(x.label)}${x.sublabel?`<div class="muted">${escapeHtml(x.sublabel)}</div>`:""}
       </button>`
    ).join("");
  }

  host.addEventListener("click",(ev)=>{
    const b = ev.target.closest("button[data-val]");
    if(!b) return;
    const val = b.getAttribute("data-val");
    closeMenu();
    onPick?.(val);
  });

  document.body.appendChild(host);
  uiState.openMenuEl = host;
  setTimeout(()=>{ document.addEventListener("click", onDocClick); },0);
  window.addEventListener("resize", closeMenu);
  window.addEventListener("scroll", closeMenu, true);
}

/* ======== Libreria ======== */
async function fetchBooks(){
  const box=$("#library-list"); if(box) box.innerHTML='<div class="muted">Carico libreria…</div>';
  try{
    const res=await fetch(`${API_BASE_URL}/books?ts=${Date.now()}`,{cache:"no-store",headers:{Accept:"application/json"}});
    if(!res.ok){const t=await res.text().catch(()=> ""); throw new Error(`HTTP ${res.status}${t?`: ${t}`:""}`);}
    const data=await res.json();
    const items = Array.isArray(data)?data:(data?.items||[]);
    uiState.books = items;
    renderLibrary(items);
    return items;
  }catch(e){
    if(box) box.innerHTML=`<div class="error">Errore: ${e.message||e}`;
    uiState.books=[];
    return [];
  }
}
function renderLibrary(books){
  const box = $("#library-list");
  if(!box) return;
  if(!books?.length){
    box.innerHTML = `<div class="muted">Nessun libro ancora. Crea il tuo primo libro con “Crea libro”.</div>`;
    return;
  }
  box.innerHTML = "";
  const grid=document.createElement("div");
  grid.className="library-grid";
  box.appendChild(grid);

  const getLastUpdated=(b)=>{
    if (b?.updated_at) return b.updated_at;
    if (Array.isArray(b?.chapters) && b.chapters.length){
      const last=[...b.chapters].sort((a,c)=>String(a?.updated_at||"").localeCompare(String(c?.updated_at||""))).slice(-1)[0];
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
    const lastUpdated = getLastUpdated(b);
    const chBadgeClass = chCount > 0 ? "badge-ok" : "badge-empty";

    const card=document.createElement("div");
    card.className="book-card";
    card.innerHTML=`
      <div class="book-title">${escapeHtml(title)}</div>
      <div class="book-meta">Autore: ${escapeHtml(author)} — Lingua: ${escapeHtml(lang)}</div>
      <div class="book-id">${escapeHtml(id)}</div>

      <div class="row-right" style="margin-top:8px;justify-content:flex-start;gap:8px;flex-wrap:wrap">
        <span class="badge ${chBadgeClass}">📄 Capitoli: ${chCount}</span>
        <span class="badge badge-neutral" title="${escapeAttr(lastUpdated || '—')}">
          🕑 Ultima mod.: ${escapeHtml(fmtLast(lastUpdated) || "—")}
        </span>
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

/* ======== Capitoli / Editor ======== */
function nextChapterId(existing=[]) {
  const nums = existing
    .map(c=>String(c.id||""))
    .map(id => (id.match(/ch_(\d{4})$/)?.[1]) )
    .filter(Boolean)
    .map(n=>parseInt(n,10));
  const max = nums.length ? Math.max(...nums) : 0;
  const n = String(max+1).padStart(4,"0");
  return `ch_${n}`;
}

async function showEditor(bookId){
  if (!uiState.books.length) { await fetchBooks(); }

  uiState.currentBookId = bookId || loadLastBook() || "";
  if(!uiState.currentBookId) return;
  rememberLastBook(uiState.currentBookId);
  $("#editor-card").style.display="block";
  $("#bookIdInput").value=uiState.currentBookId;

  const ch=$("#chapterIdInput"); if(!ch.value) ch.value="";
  const ta=$("#chapterText"); if(!ta.value) ta.value="Scrivi qui il contenuto del capitolo…";
  uiState.currentChapterId=ch.value.trim();
  uiState.lastSavedSnapshot=ta.value;

  await loadBookMeta(uiState.currentBookId);
  await refreshChaptersList(uiState.currentBookId);

  if(!(uiState.chapters?.length)){
    const nid = nextChapterId([]);
    $("#chapterIdInput").value = nid;
    uiState.currentChapterId = nid;
    $("#chapterText").focus();
  }

  startAutosave();
  syncEditorButtonState();
}
function closeEditor(){ stopAutosave(); $("#editor-card").style.display="none"; }

/* Metadati libro corrente */
async function loadBookMeta(bookId){
  try{
    const r=await fetch(`${API_BASE_URL}/books?ts=${Date.now()}`,{cache:"no-store"});
    if(!r.ok) return;
    const arr=(await r.json());
    const items=Array.isArray(arr)?arr:(arr?.items||[]);
    const bk=items.find(b=>(b?.id||b?.book_id)===bookId);
    uiState.currentLanguage = String(bk?.language || loadLastLang() || "it").toLowerCase();
    uiState.currentBookTitle = String(bk?.title || "");
  }catch{
    uiState.currentLanguage = loadLastLang() || "it";
    uiState.currentBookTitle = "";
  }
  const langEl = $("#languageInput");
  if (langEl) langEl.value = uiState.currentLanguage;
}

/* Elenco capitoli */
async function refreshChaptersList(bookId){
  const list=$("#chapters-list");
  if(list) list.innerHTML='<div class="muted">Carico capitoli…</div>';
  try{
    const r=await fetch(`${API_BASE_URL}/books?ts=${Date.now()}`,{cache:"no-store"});
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    const all=await r.json();
    const arr=Array.isArray(all)?all:(all?.items||[]);
    const found=arr.find(x=>(x?.id||x?.book_id)===bookId);
    uiState.currentBookTitle = String(found?.title || uiState.currentBookTitle || "");
    const chapters=found?.chapters||[];
    uiState.chapters=chapters.map(c=>({
      id: c?.id || "",
      title: c?.title || "",
      updated_at: c?.updated_at || "",
      path: c?.path || ""
    }));
    renderChaptersList(bookId, uiState.chapters);
  }catch(e){
    if(list) list.innerHTML=`<div class="error">Errore: ${escapeHtml(e?.message||String(e))}</div>`;
  }
}
function renderChaptersList(bookId, chapters){
  const list=$("#chapters-list");
  if(!list) return;
  if(!chapters?.length){
    list.innerHTML=`<div class="muted">Nessun capitolo ancora.</div>`;
    return;
  }
  list.innerHTML="";
  const nav=document.createElement("div");
  nav.className="row-right";
  nav.style.justifyContent="flex-start";
  nav.style.marginBottom="8px";
  nav.innerHTML=`<button class="btn btn-ghost" id="btn-ch-prev">← Precedente</button>
                 <button class="btn btn-ghost" id="btn-ch-next">Successivo →</button>`;
  list.appendChild(nav);

  const bookTitle = uiState.currentBookTitle || "";

  chapters.forEach(ch=>{
    const cid     = ch.id;
    const title   = (ch.title||"").trim();
    const shown   = title || "(senza titolo)";
    const updated = ch.updated_at||"";

    const li=document.createElement("div");
    li.className="card chapter-row";
    li.style.margin="8px 0";
    li.innerHTML=`
      <div class="chapter-head">
        <div>
          <div style="font-weight:600">${escapeHtml(shown)}</div>
          <div class="muted">
            ID: ${escapeHtml(cid)}
            ${bookTitle ? ` · Libro: ${escapeHtml(bookTitle)}` : ""}
            ${updated ? ` · ${escapeHtml(fmtLast(updated))}` : ""}
          </div>
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
  if(target && target!==uiState.currentChapterId){
    maybeAutosaveNow().finally(()=>openChapter(uiState.currentBookId,target));
  }
}

async function openChapter(bookId, chapterId){
  try{
    const r=await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}?ts=${Date.now()}`,{cache:"no-store"});
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    const data=await r.json();
    $("#bookIdInput").value=bookId;
    $("#chapterIdInput").value=chapterId;
    $("#chapterText").value=data?.content||"";
    uiState.currentBookId=bookId;
    uiState.currentChapterId=chapterId;
    uiState.lastSavedSnapshot=$("#chapterText").value;
    toast(`📖 Aperto ${chapterId}`);
  }catch(e){
    toast("Impossibile aprire il capitolo: "+(e?.message||e));
  }
}

async function deleteChapter(bookId, chapterId){
  if(!confirm(`Eliminare il capitolo ${chapterId}?`)) return;
  try{
    const r=await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`,{method:"DELETE"});
    if(!r.ok && r.status!==204) throw new Error(`HTTP ${r.status}`);
    toast("🗑️ Capitolo eliminato.");
    await refreshChaptersList(bookId);
    if(uiState.currentChapterId===chapterId){
      $("#chapterText").value="";
      uiState.currentChapterId="";
    }
  }catch(e){
    toast("Errore eliminazione: "+(e?.message||e));
  }
}

function editChapter(cid){
  $("#chapterIdInput").value=cid;
  uiState.currentChapterId=cid;
  openChapter(uiState.currentBookId,cid).then(()=>$("#chapterText")?.focus());
}

async function saveCurrentChapter(showToast=true){
  const bookId=$("#bookIdInput").value.trim();
  const chapterId=$("#chapterIdInput").value.trim();
  const content=$("#chapterText").value;
  if(!bookId || !chapterId) return toast("Inserisci Book ID e Chapter ID.");
  try{
    const r=await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`,{
      method:"PUT", headers:{ "Content-Type":"application/json" }, body:JSON.stringify({ content })
    });
    if(!r.ok){ const t=await r.text().catch(()=> ""); throw new Error(`HTTP ${r.status}${t?`: ${t}`:""}`); }
    uiState.lastSavedSnapshot=content;
    if(showToast) toast("✅ Capitolo salvato.");
    refreshChaptersList(bookId);
  }catch(e){
    toast("Errore salvataggio: "+(e?.message||e));
  }
}

/* Autosave */
function startAutosave(){ stopAutosave(); uiState.autosaveTimer=setInterval(maybeAutosaveNow,30_000); }
function stopAutosave(){ if(uiState.autosaveTimer) clearInterval(uiState.autosaveTimer); uiState.autosaveTimer=null; }
async function maybeAutosaveNow(){
  const txt=$("#chapterText")?.value ?? "";
  if(txt!==uiState.lastSavedSnapshot && uiState.currentBookId && uiState.currentChapterId){
    await saveCurrentChapter(false);
  }
}

/* ======== Export ======== */
function askFormat(defaultFmt="pdf"){
  const a=prompt("Formato? (pdf / md / txt)",defaultFmt)?.trim().toLowerCase();
  if(!a) return null;
  if(!["pdf","md","txt"].includes(a)){ toast("Formato non valido."); return null; }
  return a;
}
function downloadChapter(bookId, chapterId){
  const fmt=askFormat("pdf"); if(!fmt) return;
  window.open(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}/${fmt}`,
              "_blank","noopener");
}
async function exportBook(bookId){
  const fmt = askFormat("pdf"); if(!fmt) return;

  if (fmt === "pdf") {
    // Default: KDP-ready (6x9, no bleed). Per A4 semplice: usa classic=true
    const params = new URLSearchParams({
      trim: "6x9",
      bleed: "false",
      classic: "false"
    });
    const url = `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/export/pdf?${params.toString()}`;
    window.open(url, "_blank", "noopener");
    return;
  }

  if (fmt === "md" || fmt === "txt") {
    const url = `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/export/${fmt}`;
    window.open(url, "_blank", "noopener");
    return;
  }

  toast("Formato non supportato.");
}

/* ======== Toggle Libreria ======== */
async function toggleLibrary(force){
  const lib=$("#library-section"); if(!lib) return;
  uiState.libraryVisible=(typeof force==="boolean")?force:!uiState.libraryVisible;
  lib.style.display=uiState.libraryVisible?"block":"none";
  if(uiState.libraryVisible) await fetchBooks();
}

/* ======== Wiring ======== */
function wireButtons(){
  // CTA
  $("#btn-create-book")?.addEventListener("click",createBookSimple);
  $("#btn-library")?.addEventListener("click",()=>toggleLibrary());
  $("#btn-editor")?.addEventListener("click",()=>showEditor(loadLastBook()));

  // Toolbar editor
  $("#btn-ed-close")?.addEventListener("click",closeEditor);
  $("#btn-ed-save")?.addEventListener("click",()=>saveCurrentChapter(true));
  $("#btn-ai-generate")?.addEventListener("click",generateWithAI);
  $("#btn-ed-delete")?.addEventListener("click",async()=>{
    const bookId=$("#bookIdInput").value.trim(), chapterId=$("#chapterIdInput").value.trim();
    if(!bookId||!chapterId) return toast("Inserisci Book ID e Chapter ID.");
    await deleteChapter(bookId,chapterId);
  });

  // Input changes
  $("#chapterText")?.addEventListener("input",()=>{
    if(uiState.saveSoon) clearTimeout(uiState.saveSoon);
    uiState.saveSoon=setTimeout(maybeAutosaveNow,1500);
  });
  $("#chapterIdInput")?.addEventListener("change",async()=>{
    await maybeAutosaveNow();
    uiState.currentChapterId=$("#chapterIdInput").value.trim();
    uiState.lastSavedSnapshot=$("#chapterText").value;
  });
  $("#languageInput")?.addEventListener("change",()=>{
    const v=$("#languageInput").value.trim().toLowerCase()||"it";
    uiState.currentLanguage=v; rememberLastLang(v);
  });

  // Libreria: actions
  $("#library-list")?.addEventListener("click",async(ev)=>{
    const btn=ev.target.closest("button[data-action]"); if(!btn) return;
    const action=btn.getAttribute("data-action");
    const bookId=btn.getAttribute("data-bookid")||"";
    if(!bookId) return;
    if(action==="open"){ rememberLastBook(bookId); showEditor(bookId); }
    else if(action==="delete"){ await deleteBook(bookId); }
    else if(action==="rename"){ await renameBook(bookId, btn.getAttribute("data-oldtitle")||""); }
    else if(action==="export"){ await exportBook(bookId); }
  });

  // Editor list actions
  $("#chapters-list")?.addEventListener("click",async(ev)=>{
    const openBtn=ev.target.closest("[data-ch-open]"),
          editBtn=ev.target.closest("[data-ch-edit]"),
          delBtn =ev.target.closest("[data-ch-del]"),
          dlBtn  =ev.target.closest("[data-ch-dl]");
    if(!openBtn && !delBtn && !editBtn && !dlBtn) return;
    const cid=(openBtn||delBtn||editBtn||dlBtn).getAttribute(
      openBtn?"data-ch-open":delBtn?"data-ch-del":editBtn?"data-ch-edit":"data-ch-dl"
    );
    const bid=uiState.currentBookId || $("#bookIdInput").value.trim();
    if(!cid||!bid) return;
    if(openBtn)      await openChapter(bid,cid);
    else if(delBtn)  await deleteChapter(bid,cid);
    else if(editBtn) editChapter(cid);
    else if(dlBtn)   downloadChapter(bid,cid);
  });

  // ===== Pulsanti verdi: MENU =====
  $("#btn-book-menu")?.addEventListener("click",(ev)=>{
    if(!uiState.books.length){ toast("Nessun libro caricato."); return; }
    const items = uiState.books.map(b=>{
      const id=b?.id||b?.book_id||"";
      return { value:id, label:(b?.title||"(senza titolo)"), sublabel:`${b?.author||"—"} — ${id}` };
    });
    showMenuForButton(ev.currentTarget, items, async (val)=>{
      $("#bookIdInput").value = val;
      rememberLastBook(val);
      await showEditor(val); // ricarica capitoli del nuovo libro
    });
  });

  $("#btn-ch-menu")?.addEventListener("click",(ev)=>{
    if(!uiState.chapters.length){ toast("Nessun capitolo nel libro."); return; }
    const items = uiState.chapters.map(c=>({
      value:c.id, label:(c.title||c.id), sublabel:c.id
    }));
    showMenuForButton(ev.currentTarget, items, async (val)=>{
      $("#chapterIdInput").value = val;
      uiState.currentChapterId = val;
      await openChapter(uiState.currentBookId, val);
    });
  });

  $("#btn-ch-new")?.addEventListener("click",()=>{
    const nid = nextChapterId(uiState.chapters);
    $("#chapterIdInput").value = nid;
    uiState.currentChapterId = nid;
    $("#chapterText").focus();
    const pill = $("#nextChHint");
    if(pill) pill.textContent = nid;
  });
}

/* ===== Create/Rename/Delete book ===== */
async function createBookSimple(){
  const title=prompt("Inserisci il titolo del libro:", "Bozza Libro");
  if(title==null) return;

  let author = prompt("Nome artista", loadLastAuthor())?.trim();
  if(author==null) return;
  author = author || loadLastAuthor();
  rememberLastAuthor(author);

  let defaultLang = loadLastLang();
  let language=prompt("Lingua (es. it, en, es, fr…):", defaultLang)?.trim().toLowerCase()||defaultLang||"it";
  language=language.replace(/[^a-z-]/gi,"").slice(0,10)||"it";
  rememberLastLang(language);

  try{
    const res=await fetch(`${API_BASE_URL}/books/create`,{
      method:"POST", headers:{ "Content-Type":"application/json" }, cache:"no-store",
      body:JSON.stringify({ title:(title.trim()||"Senza titolo"), author, language, chapters:[] }),
    });
    if(!res.ok){ const txt=await res.text().catch(()=> ""); throw new Error(`HTTP ${res.status}${txt?`: ${txt}`:""}`); }
    const data=await res.json();
    rememberLastBook(data?.book_id||data?.id||"");
    toast(`✅ Libro creato (${language.toUpperCase()}) — Autore: ${author}`);
    await toggleLibrary(true);
    await fetchBooks();
    setTimeout(fetchBooks,300);
  }catch(e){
    toast("Errore di rete: "+(e?.message||e));
  }
}
async function deleteBook(bookId){
  if(!confirm("Eliminare il libro?")) return;
  try{
    const res=await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}`,{method:"DELETE"});
    if(!res.ok && res.status!==204) throw new Error(`HTTP ${res.status}`);
    toast("🗑️ Libro eliminato.");
    await fetchBooks();
  }catch(e){
    toast("Errore: "+(e?.message||e));
  }
}
async function renameBook(bookId, oldTitle){
  const newTitle=prompt("Nuovo titolo libro:",oldTitle||"")?.trim();
  if(!newTitle || newTitle===oldTitle) return;
  toast("✏️ Titolo modificato (endpoint reale in arrivo).");
}

/* ===== AI (bozza) ===== */
async function generateWithAI(){
  const bookId   = $("#bookIdInput").value.trim()||uiState.currentBookId;
  const chapterId= $("#chapterIdInput").value.trim();
  const topic    = $("#topicInput")?.value?.trim()||"";
  const language = ($("#languageInput")?.value?.trim().toLowerCase()||uiState.currentLanguage||"it");
  if(!bookId || !chapterId) return toast("Inserisci Book ID e Chapter ID.");

  uiState.currentLanguage = language;

  try{
    const r=await fetch(`${API_BASE_URL}/generate/chapter`,{
      method:"POST", headers:{ "Content-Type":"application/json" },
      body:JSON.stringify({ book_id:bookId, chapter_id:chapterId, topic, language })
    });
    if(!r.ok){ const t=await r.text().catch(()=> ""); throw new Error(`HTTP ${r.status}${t?`: ${t}`:""}`); }
    const data=await r.json();
    $("#chapterText").value=data?.content||data?.text||"";
    toast(`✨ Testo generato (bozza) — lingua: ${language.toUpperCase()}`);
    await saveCurrentChapter(false);
    await refreshChaptersList(bookId);
  }catch(e){
    toast("⚠️ AI di test: "+(e?.message||e));
  }
}

/* ===== Init ===== */
document.addEventListener("DOMContentLoaded", async ()=>{
  wireButtons();
  await pingBackend();
  await toggleLibrary(true);
  syncEditorButtonState();
});
