   /* =========================================================
    * EccomiBook — Frontend
    * src/main.js — v4.2.4 (KDP fix: download ZIP via blob, no JSON)
    * ========================================================= */
   
   import "./styles.css";
   
   /* ===== Config: API base =====
      Precedenze:
      1) window.VITE_API_BASE_URL (impostata in index.html)
      2) import.meta.env.VITE_API_BASE_URL (env di Vite)
      3) fallback production
   */
   const API_BASE_URL =
     (typeof window !== "undefined" && window.VITE_API_BASE_URL) ||
     (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
     "https://eccomibook-backend.onrender.com/api/v1";
   
   /* ===== Helpers ===== */
   const $  = (s, r=document)=>r.querySelector(s);
   const $$ = (s, r=document)=>Array.from(r.querySelectorAll(s));
   const escapeHtml = (x)=>String(x??"").replace(/[&<>"']/g, m => ({
     "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"
   }[m]));

   const escapeAttr = (s)=>escapeHtml(s).replace(/"/g,"&quot;");

// Toast minimale non-bloccante (niente alert)
const toastHostId = "__toast_host";
function toast(msg){
  try{
    let host = document.getElementById(toastHostId);
    if(!host){
      host = document.createElement("div");
      host.id = toastHostId;
      host.style.cssText = "position:fixed;bottom:12px;left:50%;transform:translateX(-50%);z-index:9999;display:flex;flex-direction:column;gap:8px;align-items:center";
      document.body.appendChild(host);
    }
    const box = document.createElement("div");
    box.textContent = String(msg||"");
    box.style.cssText = "background:#222;color:#fff;padding:8px 12px;border-radius:8px;font:14px/1.3 system-ui;box-shadow:0 4px 14px rgba(0,0,0,.2)";
    host.appendChild(box);
    setTimeout(()=>box.remove(), 2500);
  }catch{ alert(msg); }
}
   // ——— Browser helpers ———
   function supportsFetchStreaming(){
     try {
       return !!(window.ReadableStream &&
                 new Response(new ReadableStream()).body &&
                 'getReader' in Response.prototype);
     } catch { return false; }
   }
   
   function isSafariLike(){
     const ua = navigator.userAgent || "";
     const vendor = navigator.vendor || "";
     const isIOS = /iPad|iPhone|iPod/.test(ua) ||
                   (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
     const isSafari = /Safari/.test(ua) && !/Chrome|CriOS|FxiOS|Edg/.test(ua) && vendor === "Apple Computer, Inc.";
     return isIOS || isSafari;
   }
   
   /* ===== Funzioni AI ===== */
/** STREAM via fetch -> /generate/chapter/stream (Chrome/Edge/Firefox) */
async function generateWithAI(){
  const bookId    = $("#bookIdInput").value.trim() || uiState.currentBookId;
  const chapterId = $("#chapterIdInput").value.trim();
  const topic     = $("#topicInput")?.value?.trim() || "";
  const language  = ($("#languageInput")?.value?.trim().toLowerCase() || uiState.currentLanguage || "it");
  const ta        = $("#chapterText");

  if(!bookId || !chapterId) return toast("Inserisci Book ID e Chapter ID.");
  ta.value = "✍️ Sto scrivendo con l’AI (stream)…\n\n";
  ta.disabled = true;

  try{
    const payload = { book_id: bookId, chapter_id: chapterId, topic, language };
    const r = await fetch(`${API_BASE_URL}/generate/chapter/stream`,{
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(payload)
    });

    if(!r.ok) throw new Error(`HTTP ${r.status}`);

    const reader = r.body.getReader();
    ta.value = "";
    const dec = new TextDecoder("utf-8");
    while(true){
      const {done, value} = await reader.read();
      if(done) break;
      ta.value += dec.decode(value, {stream:true});
      ta.scrollTop = ta.scrollHeight; // autoscroll
    }
    toast("✨ Generazione completata (stream)");
  }catch(e){
    toast("⚠️ Errore stream: " + (e?.message||e));
  }finally{
    ta.disabled = false;
  }
}

/** SSE via EventSource -> /generate/chapter/sse (Safari/iPad consigliato) */
async function generateWithAI_SSE(){
  const bookId    = $("#bookIdInput").value.trim() || uiState.currentBookId;
  const chapterId = $("#chapterIdInput").value.trim();
  const topic     = $("#topicInput")?.value?.trim() || "";
  const language  = ($("#languageInput")?.value?.trim().toLowerCase() || uiState.currentLanguage || "it");
  const ta        = $("#chapterText");

  if(!bookId || !chapterId) return toast("Inserisci Book ID e Chapter ID.");
  ta.value = "✍️ Sto scrivendo con l’AI (SSE)…\n\n";
  ta.disabled = true;

  const url = `${API_BASE_URL}/generate/chapter/sse`
    + `?book_id=${encodeURIComponent(bookId)}`
    + `&chapter_id=${encodeURIComponent(chapterId)}`
    + `&topic=${encodeURIComponent(topic)}`
    + `&language=${encodeURIComponent(language)}`;

  return new Promise((resolve,reject)=>{
    const es = new EventSource(url);
    ta.value = "";

    es.onmessage = (ev)=>{
      ta.value += ev.data;
      ta.scrollTop = ta.scrollHeight;
    };

    es.addEventListener("done", ()=>{
      es.close();
      ta.disabled = false;
      toast("✨ Generazione completata (SSE)");
      resolve();
    });

    es.addEventListener("error", (e)=>{
      es.close();
      ta.disabled = false;
      toast("⚠️ Errore SSE");
      reject(e);
    });
  });
}

/** Autoswitch: sceglie automaticamente tra stream fetch e SSE */
async function generateWithAI_auto(){
  const mode = (!isSafariLike() && supportsFetchStreaming()) ? "fetch-stream" : "sse";
  console.log("AI mode:", mode);
  return mode === "fetch-stream" ? generateWithAI() : generateWithAI_SSE();
}
// ===== Local AI-like fallback (outline generator) =====
function localDraftFromTopic(topic="", language="it", chapterId="") {
  const L = (lang=>{
    lang = (lang||"it").toLowerCase();
    if (lang.startsWith("en")) return {
      chapter:"Chapter", untitled:"Untitled",
      goal:"## Goal\nDescribe the purpose and the learning outcome.",
      why:"## Why it matters\nContext, benefits, expected impact.",
      steps:"## Practical steps\n1) …\n2) …\n3) …",
      tips:"## Tips & best practices\n- …\n- …",
      pitfalls:"## Common pitfalls\n- …",
      summary:"## Key takeaways\n- …\n- …",
      exercise:"## Exercise\nWrite a short example applying the above points."
    };
    if (lang.startsWith("es")) return {
      chapter:"Capítulo", untitled:"Sin título",
      goal:"## Objetivo\nDescribe el propósito y lo que aprenderá el lector.",
      why:"## Por qué importa\nContexto, beneficios e impacto esperado.",
      steps:"## Pasos prácticos\n1) …\n2) …\n3) …",
      tips:"## Consejos y buenas prácticas\n- …\n- …",
      pitfalls:"## Errores comunes\n- …",
      summary:"## Ideas clave\n- …\n- …",
      exercise:"## Ejercicio\nEscribe un ejemplo aplicando los puntos anteriores."
    };
    return {
      chapter:"Capitolo", untitled:"Senza titolo",
      goal:"## Obiettivo\nDescrivi scopo e risultato di apprendimento.",
      why:"## Perché è importante\nContesto, benefici, impatto atteso.",
      steps:"## Passi pratici\n1) …\n2) …\n3) …",
      tips:"## Consigli & best practice\n- …\n- …",
      pitfalls:"## Errori comuni\n- …",
      summary:"## Takeaway\n- …\n- …",
      exercise:"## Esercizio\nScrivi un esempio applicando i punti sopra."
    };
  })(language);

  const t = (topic||"").replace(/\s+\.$/,"");
  const title = t ? `${L.chapter}: ${t}` : `${L.chapter}: ${L.untitled}`;
  return `# ${title}${chapterId?` (${chapterId})`:""}\n\n${L.goal}\n\n${L.why}\n\n${L.steps}\n\n${L.tips}\n\n${L.pitfalls}\n\n${L.summary}\n\n${L.exercise}\n`;
}

/* ===== Local storage ===== */
const rememberLastBook   = (id)=>{ try{ localStorage.setItem("last_book_id", id||""); }catch{} };
const loadLastBook       = ()=>{ try{ return localStorage.getItem("last_book_id")||""; }catch{ return ""; } };
const rememberLastLang   = (lang)=>{ try{ localStorage.setItem("last_language", String(lang||"").toLowerCase()); }catch{} };
const loadLastLang       = ()=>{ try{ return (localStorage.getItem("last_language")||"it").toLowerCase(); }catch{ return "it"; } };
const rememberLastAuthor = (a)=>{ try{ localStorage.setItem("last_author", a||"Nome artista"); }catch{} };
const loadLastAuthor     = ()=>{ try{ return localStorage.getItem("last_author") || "Nome artista"; }catch{ return "Nome artista"; } };

/* ===== UI state ===== */
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

function resetEditorForBook(bookId){
  uiState.currentBookId    = bookId || "";
  uiState.currentChapterId = "";
  uiState.currentBookTitle = "";
  uiState.lastSavedSnapshot = "";

  const ch  = $("#chapterIdInput");
  const ta  = $("#chapterText");
  const ttl = $("#chapterTitleInput");      // 👈 aggiungi

  if (ch)  ch.value = "";
  if (ta) {
    ta.value = "";
    ta.placeholder = "Scrivi qui il contenuto del capitolo…";
  }
  if (ttl) ttl.value = "";                  // 👈 aggiungi
}

/* ===== Date utils ===== */
const fmtLast = (iso)=>{
  if(!iso) return "";
  const d = new Date(iso); if(isNaN(d)) return iso;
  const pad = n=>String(n).padStart(2,"0");
  return `${pad(d.getDate())}/${pad(d.getMonth()+1)}/${d.getFullYear()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
};
const fmtHHMM = (d=new Date())=>{
  const pad=n=>String(n).padStart(2,"0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
};

// ===== Feature flags =====
const USE_MODAL_RENAME = false;
const ENABLE_CHAPTER_DOWNLOAD = false; // ⬅️ disattiva “Scarica” nei capitoli

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
    const tryFetch = async (path) => {
      const res = await fetch(`${API_BASE_URL}${path}`, { mode:"cors", cache:"no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json().catch(()=> ({}));
    };
    let data = await tryFetch("/ping").catch(()=>null);
    if (!(data && (data.pong || data.ok))) data = await tryFetch("/health");
    renderStatus({mode:"ok", title:"EccomiBook Live", sub:`Ultimo aggiornamento: ${fmtHHMM()}`});
    console.log("✅ Backend online", data);
  }catch(e){
    renderStatus({mode:"ko", title:"EccomiBook Offline", sub:"Servizio non raggiungibile"});
    console.warn("❌ Backend offline:", e);
  }
}

/* ===== Menu popup custom (clamp + flip) ===== */
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
  host.style.position = "absolute";
  host.style.visibility = "hidden";
  host.style.left = "0px";
  host.style.top  = "0px";

  host.innerHTML = items.length
    ? items.map(x =>
        `<button type="button" data-val="${escapeAttr(x.value)}">
           ${escapeHtml(x.label)}${x.sublabel?`<div class="muted">${escapeHtml(x.sublabel)}</div>`:""}
         </button>`
      ).join("")
    : `<div class="muted" style="padding:6px 8px">Nessun elemento</div>`;

  document.body.appendChild(host);

  const margin = 12;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const scrollX = window.scrollX || document.documentElement.scrollLeft || 0;
  const scrollY = window.scrollY || document.documentElement.scrollTop || 0;

  const mw = Math.min(host.offsetWidth || 280, vw - margin*2);
  const mh = Math.min(host.offsetHeight || 200, vh - margin*2);
  host.style.maxWidth = `min(560px, ${vw - margin*2}px)`;
  host.style.maxHeight = `${vh - margin*2}px`;
  host.style.overflow = "auto";
  host.style.zIndex = "1000";

  let left = rect.left + scrollX;
  left = Math.min(left, scrollX + vw - mw - margin);
  left = Math.max(left, scrollX + margin);

  const spaceBelow = (scrollY + vh) - (rect.bottom + scrollY);
  const wantBelow = spaceBelow >= mh + margin;
  let top = wantBelow ? (rect.bottom + scrollY + 6) : (rect.top + scrollY - mh - 6);

  top = Math.max(top, scrollY + margin);
  top = Math.min(top, scrollY + vh - mh - margin);

  host.style.left = `${left}px`;
  host.style.top  = `${top}px`;
  host.style.visibility = "visible";

  host.addEventListener("click",(ev)=>{
    const b = ev.target.closest("button[data-val]");
    if(!b) return;
    const val = b.getAttribute("data-val");
    closeMenu();
    onPick?.(val);
  });

  uiState.openMenuEl = host;
  setTimeout(()=>{ document.addEventListener("click", onDocClick); },0);
  window.addEventListener("resize", closeMenu);
  window.addEventListener("scroll", closeMenu, true);
}

/* ===== Libreria ===== */
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

// === API helper: crea capitolo sul backend (POST) ===
async function apiCreateChapter(
  bookId,
  { title = "Nuovo capitolo", content = "", language } = {}
) {
  const r = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, content, language })
  });
  if (!r.ok) {
    const t = await r.text().catch(() => "");
    throw new Error(`HTTP ${r.status}${t ? `: ${t}` : ""}`);
  }
  // Risposta attesa: { ok:true, chapter:{ id,title,content,language }, count }
  return r.json();
}

/* ===== Capitoli / Editor ===== */
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

  const idToOpen = bookId || loadLastBook() || "";
  if(!idToOpen) return;

  rememberLastBook(idToOpen);
  $("#editor-card").style.display="block";
  resetEditorForBook(idToOpen);          // 👈 pulizia qui
  $("#bookIdInput").value = idToOpen;

  await loadBookMeta(idToOpen);
  await refreshChaptersList(idToOpen);
  tweakChapterEditorUI();

  if(!(uiState.chapters?.length)){
    const nid = nextChapterId([]);
    $("#chapterIdInput").value = nid;
    uiState.currentChapterId = nid;
    $("#chapterText").focus();
  }

  startAutosave();
  syncEditorButtonState();
}

function closeEditor(){
  try{ stopAutosave(); }catch{}
  const card = $("#editor-card");
  if (card){
    card.style.display = "none";
    card.setAttribute("hidden","true");
    card.setAttribute("aria-hidden","true");
  }

  // reset stato editor per evitare autosave fantasma
  uiState.currentChapterId  = "";
  uiState.lastSavedSnapshot = "";
  const ch  = $("#chapterIdInput");
  const ta  = $("#chapterText");
  const ttl = $("#chapterTitleInput");
  if (ch)  ch.value = "";
  if (ttl) ttl.value = "";
  if (ta)  ta.value = "";
}

/* HERO helpers */
function syncEditorButtonState(){
  const editorBtn = $("#btn-editor"); if(!editorBtn) return;
  const hasBook = !!(loadLastBook());
  editorBtn.disabled = !hasBook;
  editorBtn.title = hasBook ? "Scrivi e salva capitoli" : "Apri un libro dalla Libreria";
  editorBtn.classList.toggle("is-disabled", !hasBook);
}

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

  // Navigazione veloce
  const nav=document.createElement("div");
  nav.className="row-right";
  nav.style.justifyContent="flex-start";
  nav.style.marginBottom="8px";
  nav.innerHTML=`<button class="btn btn-ghost" id="btn-ch-prev">← Precedente</button>
                 <button class="btn btn-ghost" id="btn-ch-next">Successivo →</button>`;
  list.appendChild(nav);

  const bookTitle = uiState.currentBookTitle || "";

  // Lista capitoli DnD
  const ul = document.createElement("div");
  ul.setAttribute("role","list");
  list.appendChild(ul);

  chapters.forEach(ch=>{
    const cid     = ch.id;
    const title   = (ch.title||"").trim();
    const shown   = title || "(senza titolo)";
    const updated = ch.updated_at||"";

    const row=document.createElement("div");
    row.className="card chapter-row dnd-row";
    row.style.margin="8px 0";
    row.draggable = true;
    row.dataset.cid = cid;

    row.innerHTML = `
  <div class="dnd-head">
    <button class="drag-handle" title="Trascina per riordinare" aria-label="Trascina">⠿</button>
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
  </div>
  <div class="chapter-actions">
    <!-- ✅ NUOVO: apre la modale con il PDF del capitolo -->
    <button class="btn btn-secondary btn-preview"
            data-bid="${escapeAttr(bookId)}"
            data-cid="${escapeAttr(cid)}">📖 Anteprima</button>

    <button class="btn btn-secondary" data-ch-open="${escapeAttr(cid)}">Apri</button>
    <button class="btn btn-ghost"     data-ch-edit="${escapeAttr(cid)}">Modifica</button>
    <button class="btn btn-ghost"     data-ch-del="${escapeAttr(cid)}">Elimina</button>
    ${ENABLE_CHAPTER_DOWNLOAD ? `<button class="btn btn-ghost" data-ch-dl="${escapeAttr(cid)}">Scarica</button>` : ``}
  </div>`;
    ul.appendChild(row);
  });

  // DnD wiring
  enableChapterDragAndDrop(ul, async (newOrder)=>{
    try{
      await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/reorder`,{
        method:"POST",
        headers:{ "Content-Type":"application/json" },
        body: JSON.stringify({ order: newOrder })
      });
      uiState.chapters.sort((a,b)=> newOrder.indexOf(a.id) - newOrder.indexOf(b.id));
      toast("✅ Ordine capitoli salvato.");
    }catch(e){
      toast("Errore salvataggio ordine: "+(e?.message||e));
      refreshChaptersList(bookId);
    }
  });

  $("#btn-ch-prev")?.addEventListener("click",()=>stepChapter(-1));
  $("#btn-ch-next")?.addEventListener("click",()=>stepChapter(+1));
}

function enableChapterDragAndDrop(container, onCommit){
  let dragging = null;
  let placeholder = document.createElement("div");
  placeholder.className = "drop-hint";

  container.addEventListener("dragstart", (e)=>{
    const row = e.target.closest(".dnd-row");
    if(!row) return;
    dragging = row;
    row.classList.add("dragging");
    e.dataTransfer.effectAllowed = "move";
    try{ e.dataTransfer.setData("text/plain", row.dataset.cid || ""); }catch{}
  });

  container.addEventListener("dragend", ()=>{
    dragging?.classList.remove("dragging");
    dragging = null;
    placeholder.remove();
  });

  container.addEventListener("dragover", (e)=>{
    if(!dragging) return;
    e.preventDefault();
    const after = getRowAfter(container, e.clientY);
    if(after == null){
      container.appendChild(placeholder);
    }else{
      container.insertBefore(placeholder, after);
    }
  });

  container.addEventListener("drop", async (e)=>{
    e.preventDefault();
    if(!dragging) return;
    const after = getRowAfter(container, e.clientY);
    if(after == null){
      container.appendChild(dragging);
    }else{
      container.insertBefore(dragging, after);
    }
    placeholder.remove();

    const order = Array.from(container.querySelectorAll(".dnd-row")).map(r=>r.dataset.cid);
    await onCommit?.(order);
  });

  function getRowAfter(container, y){
    const rows = [...container.querySelectorAll(".dnd-row:not(.dragging)")];
    return rows.find(row=>{
      const box = row.getBoundingClientRect();
      return y <= box.top + box.height/2;
    }) || null;
  }

  container.addEventListener("mousedown",(e)=>{
    const handle = e.target.closest(".drag-handle");
    if(!handle) return;
    const row = handle.closest(".dnd-row");
    if(row){
      row.draggable = true;
    }
  });
}

/* Navigazione tra capitoli */
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

/* ===== Apri capitolo ===== */
async function openChapter(bookId, chapterId){
  try{
    const r = await fetch(
      `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}?ts=${Date.now()}`,
      { cache: "no-store" }
    );
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();

    $("#bookIdInput").value    = bookId;
    $("#chapterIdInput").value = chapterId;

    $("#chapterText").value       = data?.content || "";
    $("#chapterText").placeholder = "Scrivi qui il contenuto del capitolo…";

    const titleEl = $("#chapterTitleInput");
    if (titleEl) titleEl.value = data?.title || "";

    uiState.currentBookId     = bookId;
    uiState.currentChapterId  = chapterId;
    uiState.lastSavedSnapshot = getEditorSnapshot();

    // 🔄 reset debounce autosave (evita autosave fantasma subito dopo l’apertura)
    if (uiState.saveSoon) {
      clearTimeout(uiState.saveSoon);
      uiState.saveSoon = null;
    }

    toast(`📖 Aperto ${chapterId}`);
    tweakChapterEditorUI();
  }catch(e){
    toast("Impossibile aprire il capitolo: " + (e?.message || e));
  }
}

/* ===== Delete/Edit capitolo ===== */
async function deleteChapter(bookId, chapterId){
  if(!confirm(`Eliminare il capitolo ${chapterId}?`)) return;
  try{
    const r = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`, { method: "DELETE" });
    if(!r.ok && r.status!==204) throw new Error(`HTTP ${r.status}`);
    toast("🗑️ Capitolo eliminato.");

    await refreshChaptersList(bookId);
    if(uiState.currentChapterId===chapterId){
      $("#chapterText").value="";
      uiState.currentChapterId="";
    }
    await fetchBooks();
  }catch(e){
    toast("Errore eliminazione: "+(e?.message||e));
  }
}
function editChapter(cid){
  $("#chapterIdInput").value=cid;
  uiState.currentChapterId=cid;
  openChapter(uiState.currentBookId,cid).then(()=>$("#chapterText")?.focus());
}

/* ===== Save capitolo ===== */
// Snapshot editor = content + title (stringa serializzata)
function getEditorSnapshot(){
  const content = $("#chapterText")?.value ?? "";
  const title   = $("#chapterTitleInput")?.value?.trim() ?? "";
  return JSON.stringify({ content, title });
}

async function saveCurrentChapter(showToast=true){
  const bookId    = $("#bookIdInput").value.trim();
  const chapterId = $("#chapterIdInput").value.trim();
  let content     = $("#chapterText").value;
  const title     = ($("#chapterTitleInput")?.value || "").trim();

  if (content === "Scrivi qui il contenuto del capitolo…") content = "";
  if(!bookId) return toast("Inserisci Book ID.");
  if(!chapterId) return toast("Inserisci Chapter ID.");

  // 👇 Se il capitolo NON esiste ancora, prima lo CREO
  const exists = uiState.chapters.some(c => c.id === chapterId);
  try{
    if (!exists) {
      const res = await apiCreateChapter(bookId, { title, content, language: uiState.currentLanguage });
      const ch  = res?.chapter;
      if (!ch?.id) throw new Error("Creazione capitolo fallita (ID mancante).");

      // aggiorno UI con l'ID restituito dal backend
      $("#chapterIdInput").value = ch.id;
      uiState.currentChapterId   = ch.id;

      uiState.lastSavedSnapshot  = getEditorSnapshot();
      if (showToast) toast("✅ Capitolo creato.");
      await refreshChaptersList(bookId);
      await fetchBooks();
      return; // niente PUT: abbiamo già salvato contenuto+titolo via POST
    }

    // 👇 Se esiste già, aggiorno (PUT)
    const payload = { content, title };
    const r = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`,{
      method:"PUT",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(payload)
    });
    if(!r.ok){
      const t=await r.text().catch(()=> "");
      throw new Error(`HTTP ${r.status}${t?`: ${t}`:""}`);
    }

    uiState.lastSavedSnapshot = getEditorSnapshot();
    if(showToast) toast("✅ Capitolo salvato.");
    await refreshChaptersList(bookId);
    await fetchBooks();
  }catch(e){
    toast("Errore salvataggio: "+(e?.message||e));
  }
}

/* ===== Autosave ===== */
async function maybeAutosaveNow(){
  const snapshot = getEditorSnapshot();
  if (snapshot !== uiState.lastSavedSnapshot &&
      uiState.currentBookId && uiState.currentChapterId) {
    try {
      await saveCurrentChapter(false);
    } catch(e) {
      console.warn("Autosave skipped:", e?.message||e);
    }
  }
}

// ===== Autosave timing (debounce + safety interval) =====
const AUTOSAVE_DEBOUNCE_MS = 180000; // 3 minuti di inattività

function bumpAutosaveTimer(){
  if (uiState.saveSoon) clearTimeout(uiState.saveSoon);
  uiState.saveSoon = setTimeout(maybeAutosaveNow, AUTOSAVE_DEBOUNCE_MS);
}

let _autoInterval = null;
function startAutosave(){
  if (_autoInterval) return;
  // Salvataggio di sicurezza ogni 5 minuti anche se l'utente scrive di continuo
  _autoInterval = setInterval(maybeAutosaveNow, 300000);
}
function stopAutosave(){
  if (_autoInterval){ clearInterval(_autoInterval); _autoInterval = null; }
  if (uiState.saveSoon){ clearTimeout(uiState.saveSoon); uiState.saveSoon = null; }
}

/* ===== Export (LIBRI interi) ===== */
const EXPORT_FORMATS = [
  { label: "📄 PDF", value: "pdf" },
  { label: "📘 KDP", value: "kdp" },
  { label: "📝 Markdown", value: "md" },
  { label: "📃 TXT", value: "txt" }
];

/* ===== Export (CAPITOLI singoli) ===== */
const CHAPTER_EXPORT_FORMATS = [
  // { label: "📄 PDF", value: "pdf" }, // ← sblocca solo se hai attivato l'endpoint PDF
  { label: "📝 Markdown", value: "md" },
  { label: "📃 TXT", value: "txt" }
];

// Scarica capitolo con check preventivo + menu formati
async function downloadChapter(bookId, chapterId, anchorBtn, {debug=false} = {}) {
  const bid = bookId || uiState.currentBookId || $("#bookIdInput")?.value?.trim();
  const cid = chapterId || uiState.currentChapterId || $("#chapterIdInput")?.value?.trim();

  if (!bid) return toast("Manca il Book ID");
  if (!cid) return toast("Manca il Chapter ID");

  console.log("[downloadChapter] bookId:", bid, "chapterId:", cid);

  // 1️⃣ Verifica che il capitolo esista davvero sul backend
  try {
    const chk = await fetch(
      `${API_BASE_URL}/books/${encodeURIComponent(bid)}/chapters/${encodeURIComponent(cid)}?ts=${Date.now()}`,
      { cache: "no-store" }
    );
    if (!chk.ok) {
      const t = await chk.text().catch(() => "");
      toast(`Capitolo non trovato (${chk.status}). ${t?.slice(0, 120) || ""}`);
      return;
    }
  } catch (e) {
    toast("Errore di rete nel check capitolo: " + (e?.message || e));
    return;
  }

  // 2️⃣ Menu formati + apertura URL corretta
  showMenuForButton(anchorBtn || document.body, CHAPTER_EXPORT_FORMATS, async (fmt) => {
    const url = `${API_BASE_URL}/books/${encodeURIComponent(bid)}/chapters/${encodeURIComponent(cid)}.${fmt}`;
    console.log("[downloadChapter] URL:", url);

    if (DEBUG_EXPORT && debug) {
      await fetchAndInspect(url, `chapter_${cid}.${fmt}`);
    } else {
      window.open(url, "_blank", "noopener");
    }
  });
}

function exportBook(bookId, anchorBtn){
  showMenuForButton(anchorBtn || document.body, EXPORT_FORMATS, async (fmt)=>{
    const base = `${API_BASE_URL}/export/books/${encodeURIComponent(bookId)}/export`;
    try {
      if (fmt === "kdp") {
        // ZIP: sempre via fetch+blob per compatibilità Safari
        await fetchAndDownload(`${base}/kdp`, `book_${bookId}_kdp.zip`);
        return;
      }

      // pdf / md / txt
      const url  = `${base}/${fmt}`;
      const name = `book_${bookId}.${fmt}`;

      if (isSafariLike()) {
        // Safari/iPad: fetch+blob
        await fetchAndDownload(url, name);
      } else {
        // Browser “liberi”: prova fast-path con window.open
        const win = window.open(url, "_blank", "noopener");
        // Se popup bloccato, fallback a fetch+blob
        if (!win || win.closed || typeof win.closed === "undefined") {
          await fetchAndDownload(url, name);
        }
      }
    } catch (e) {
      toast("Errore export: " + (e?.message || e));
    }
  });
}

// Helpers per download
function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "";
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(url); a.remove(); }, 0);
}

// ===== DEBUG EXPORT =====
const DEBUG_EXPORT = true;

function _looksBinary(ct=""){
  return /pdf|zip|octet-stream|application\/(?!json)/i.test(ct);
}

async function fetchAndInspect(url, fallbackName="download.bin"){
  const t0 = performance.now();
  const res = await fetch(url, { cache: "no-store" });
  const ct  = res.headers.get("content-type") || "";
  const cd  = res.headers.get("content-disposition") || "";
  const ok  = res.ok;

  // prova a ricavare il filename da Content-Disposition
  let name = fallbackName;
  const m = /filename\*=UTF-8''([^;]+)|filename="?([^"]+)"?/i.exec(cd || "");
  if (m) name = decodeURIComponent(m[1] || m[2] || fallbackName);

  // scarico il blob
  const blob = await res.blob();
  const size = blob.size;

  console.log("[EXPORT][HEADERS]", { ok, status: res.status, ct, cd, size, url });

  // se testuale provo a leggere le prime righe
  if (!_looksBinary(ct)) {
    const txt = await blob.text();
    console.log("[EXPORT][PREVIEW]", txt.slice(0, 500));
  } else {
    // preview esadecimale dei primi byte (PDF/ZIP ecc.)
    const ab  = await blob.arrayBuffer();
    const view = new Uint8Array(ab.slice(0, 64));
    const hex  = Array.from(view).map(b=>b.toString(16).padStart(2,"0")).join(" ");
    console.log("[EXPORT][BYTES]", hex);
  }

  console.log("[EXPORT][TIME]", Math.round(performance.now()-t0)+"ms");

  // comunque forzo il download locale (mantengo il content-type)
  triggerDownload(blob, name);
}

// === Helper download universale ===
async function fetchAndDownload(url, fallbackName = "download.bin"){
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  let name = fallbackName;
  const cd = res.headers.get("content-disposition") || "";
  const m  = /filename\*=UTF-8''([^;]+)|filename="?([^"]+)"?/i.exec(cd);
  if (m) { try { name = decodeURIComponent(m[1] || m[2] || fallbackName); } catch {} }
  const blob = await res.blob();
  triggerDownload(blob, name);
}

/* ===== Toggle Libreria ===== */
async function toggleLibrary(force){
  const lib=$("#library-section"); if(!lib) return;
  uiState.libraryVisible=(typeof force==="boolean")?force:!uiState.libraryVisible;
  lib.style.display=uiState.libraryVisible?"block":"none";
  if(uiState.libraryVisible) await fetchBooks();
}

/* ===== Wiring ===== */
function wireButtons(){
  // evita doppio binding se la funzione viene richiamata due volte
  if (wireButtons._bound) return;
  wireButtons._bound = true;

  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", ()=>toggleLibrary());
  $("#btn-editor")?.addEventListener("click", ()=>showEditor(loadLastBook()));

  // nel wireButtons()
  $("#btn-ed-close")?.addEventListener("click", async (e)=>{
  e.preventDefault();
  e.stopPropagation();
  try { await maybeAutosaveNow(); } catch(err){
    console.warn("Autosave skipped on close:", err?.message||err);
  }
  closeEditor();
  document.getElementById("library-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
  await toggleLibrary(true);
});
  $("#btn-ed-save")?.addEventListener("click", ()=>saveCurrentChapter(true));
  $("#btn-ai-generate")?.addEventListener("click", async ()=>{
  const mode = (!isSafariLike() && supportsFetchStreaming()) ? "fetch-stream" : "sse";
  console.log("[AI button] mode:", mode,
              "| isSafariLike:", isSafariLike(),
              "| supportsFetchStreaming:", supportsFetchStreaming());
  await generateWithAI_auto();
});

  $("#btn-ed-delete")?.addEventListener("click", async ()=>{
    const bookId = $("#bookIdInput").value.trim();
    const chapterId = $("#chapterIdInput").value.trim();
    if(!bookId || !chapterId) return toast("Inserisci Book ID e Chapter ID.");
    await deleteChapter(bookId, chapterId);
  });

  $("#chapterIdInput")?.addEventListener("change", async ()=>{
    await maybeAutosaveNow();
    uiState.currentChapterId = $("#chapterIdInput").value.trim();
    uiState.lastSavedSnapshot = getEditorSnapshot();
  });

  $("#languageInput")?.addEventListener("change", ()=>{
    const v = $("#languageInput").value.trim().toLowerCase() || "it";
    uiState.currentLanguage = v;
    rememberLastLang(v);
  });

   // listener debounce 3 minuti
$("#chapterText")?.addEventListener("input", bumpAutosaveTimer);

// il titolo viene creato dopo: uso delega
document.addEventListener("input", (e)=>{
  if (e.target && e.target.id === "chapterTitleInput") {
    bumpAutosaveTimer();
  }
});
   
  $("#library-list")?.addEventListener("click", async (ev)=>{
  const btn = ev.target.closest("button[data-action]");
  if(!btn) return;

  const action = btn.getAttribute("data-action");
  const bookId = btn.getAttribute("data-bookid") || "";
  if(!bookId) return;

  if (action === "open") {
    rememberLastBook(bookId);
    showEditor(bookId);
  }
  else if (action === "delete") {
    await deleteBook(bookId);
  }
  else if (action === "rename") {
    if (USE_MODAL_RENAME && typeof openEditBookModal === "function") {
      openEditBookModal(bookId);
    } else {
      // fallback: prompt
      await renameBook(bookId, btn.getAttribute("data-oldtitle") || "");
    }
  }
  else if (action === "export") {
    await exportBook(bookId, btn);
  }
});

  $("#chapters-list")?.addEventListener("click", async (ev)=>{
    const openBtn = ev.target.closest("[data-ch-open]"),
          editBtn = ev.target.closest("[data-ch-edit]"),
          delBtn  = ev.target.closest("[data-ch-del]"),
          dlBtn   = ev.target.closest("[data-ch-dl]");
    if(!openBtn && !delBtn && !editBtn && !dlBtn) return;

    const cid = (openBtn||delBtn||editBtn||dlBtn).getAttribute(
      openBtn ? "data-ch-open" : delBtn ? "data-ch-del" : editBtn ? "data-ch-edit" : "data-ch-dl"
    );
    const bid = uiState.currentBookId || $("#bookIdInput").value.trim();
    if(!cid || !bid) return;

    if (openBtn)       await openChapter(bid, cid);
    else if (delBtn)   await deleteChapter(bid, cid);
    else if (editBtn)  editChapter(cid);
    else if (dlBtn)    downloadChapter(bid, cid, dlBtn, { debug: ev.altKey });
  });

  $("#btn-book-menu")?.addEventListener("click", (ev)=>{
    if(!uiState.books.length){ toast("Nessun libro caricato."); return; }
    const items = uiState.books.map(b=>{
      const id=b?.id||b?.book_id||"";
      return { value:id, label:(b?.title||"(senza titolo)"), sublabel:`${b?.author||"—"} — ${id}` };
    });
    showMenuForButton(ev.currentTarget, items, async (val)=>{
      $("#bookIdInput").value = val;
      rememberLastBook(val);
      await showEditor(val);
    });
  });

  $("#btn-ch-menu")?.addEventListener("click", (ev)=>{
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

  // --- Nuovo capitolo via MODAL ---
  const newChModal = $("#new-chapter-modal");
  const newChForm  = $("#new-chapter-form");
  let _lastActiveEl = null;

  const openNewChModal = ()=>{
    const bookId = uiState.currentBookId || $("#bookIdInput").value.trim();
    if (!bookId) { toast("Apri prima un libro."); return; }
    _lastActiveEl = document.activeElement;
    newChForm?.reset();
    newChModal?.removeAttribute("hidden");
    newChModal?.classList.add("is-open");
    document.body.classList.add("modal-open");
    newChForm?.querySelector('[name="title"]')?.focus();
  };

  const closeNewChModal = ()=>{
    newChModal?.classList.remove("is-open");
    newChModal?.setAttribute("hidden","true");
    document.body.classList.remove("modal-open");
    _lastActiveEl?.focus?.();
    _lastActiveEl = null;
  };

  $("#btn-ch-new")?.addEventListener("click",(e)=>{
    e.preventDefault();
    openNewChModal();
  });

  $("#btn-newch-cancel")?.addEventListener("click", closeNewChModal);
  $("#btn-newch-cancel-2")?.addEventListener("click", closeNewChModal);
  newChModal?.querySelector(".modal__backdrop")?.addEventListener("click", closeNewChModal);

  newChForm?.addEventListener("submit", async (ev)=>{
    ev.preventDefault();
    const bookId = uiState.currentBookId || $("#bookIdInput").value.trim();
    if (!bookId) { toast("Apri prima un libro."); return; }
    const title  = newChForm.title.value.trim();
    const topic  = newChForm.topic.value.trim();
    const autoAI = newChForm.autoAI.checked;

    try {
      const res = await apiCreateChapter(bookId, { title, content:"", language: uiState.currentLanguage });
      const ch  = res?.chapter;
      if (!ch?.id) throw new Error("ID capitolo mancante nella risposta");

      $("#chapterIdInput").value = ch.id;
      uiState.currentChapterId   = ch.id;

      $("#chapterText").value    = "";
      const titleInput = $("#chapterTitleInput");        // 👈 nuovo
      if (titleInput) titleInput.value = title;          // 👈 nuovo

      uiState.lastSavedSnapshot  = getEditorSnapshot();  // 👈 usa snapshot

      await refreshChaptersList(bookId);
      await fetchBooks();

      closeNewChModal();
      $("#chapterText").focus();

      if (autoAI) {
  $("#topicInput").value = topic;
  const mode = (!isSafariLike() && supportsFetchStreaming()) ? "fetch-stream" : "sse";
  console.log("[AI modal] mode:", mode);
  await generateWithAI_auto();
}

      const pill = $("#nextChHint");
      if (pill) pill.textContent = ch.id;
      toast(`🆕 Creato ${ch.id}`);
    } catch (e) {
      toast("Errore creazione capitolo: " + (e?.message || e));
    }
  });

  // Scorciatoie modale: ESC chiude, Invio su "Titolo" invia
  document.addEventListener("keydown", (e)=>{
    if (e.key === "Escape" && newChModal?.classList.contains("is-open")) {
      closeNewChModal();
    }
  });
  newChForm?.querySelector('[name="title"]')?.addEventListener("keydown",(e)=>{
    if (e.key === "Enter") { e.preventDefault(); newChForm?.requestSubmit?.(); }
  });
} // ⟵ chiusura wireButtons

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
    const res=await fetch(`${API_BASE_URL}/books`,{
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      cache:"no-store",
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
  const b = uiState.books.find(x=>(x?.id||x?.book_id)===bookId) || {};
  const curAuthor  = b?.author || loadLastAuthor();
  const curLang    = (b?.language || loadLastLang() || "it").toLowerCase();

  const newTitle = prompt("Nuovo titolo libro:", oldTitle || b?.title || "")?.trim();
  if(newTitle==null) return;

  const newAuthor = prompt("Autore:", curAuthor)?.trim();
  if(newAuthor==null) return;

  let newLang = prompt("Lingua (es. it, en, es, fr…):", curLang)?.trim().toLowerCase();
  if(newLang==null) return;
  newLang = (newLang||curLang||"it").replace(/[^a-z-]/gi,"").slice(0,10) || "it";

  try{
    const r = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}`,{
      method:"PATCH",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify({ title:newTitle, author:newAuthor, language:newLang })
    });
    if(!r.ok){ const t=await r.text().catch(()=> ""); throw new Error(`HTTP ${r.status}${t?`: ${t}`:""}`); }

    rememberLastAuthor(newAuthor);
    rememberLastLang(newLang);

    toast("✅ Libro aggiornato.");
    await fetchBooks();

    if(uiState.currentBookId===bookId){
      uiState.currentBookTitle = newTitle;
      uiState.currentLanguage  = newLang;
      const langEl=$("#languageInput"); if(langEl) langEl.value=newLang;
      await refreshChaptersList(bookId);
    }
  }catch(e){
    toast("Errore aggiornamento: "+(e?.message||e));
  }
}

/* =========================================================
 * EccomiBook — Anteprima capitolo PDF (singolo)
 * ========================================================= */

// === 1. Funzioni per aprire/chiudere la modale ===
function openPdfPreview(url) {
  const modal = document.getElementById("pdfPreviewModal");
  const frame = document.getElementById("pdfPreviewFrame");
  if (!modal || !frame) return;

  frame.src = url;
  modal.style.display = "block";
  document.body.style.overflow = "hidden"; // blocca scroll sotto
}

function closePdfPreview() {
  const modal = document.getElementById("pdfPreviewModal");
  const frame = document.getElementById("pdfPreviewFrame");
  if (!modal || !frame) return;

  frame.src = "about:blank";
  modal.style.display = "none";
  document.body.style.overflow = "";
}

// === 2. Eventi di chiusura modale ===
document.getElementById("pdfPreviewClose")?.addEventListener("click", closePdfPreview);
document.getElementById("pdfPreviewModal")?.addEventListener("click", (e) => {
  if (e.target.id === "pdfPreviewModal") closePdfPreview(); // click su sfondo
});
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closePdfPreview();
});

// === 3. Pulsante “📖 Anteprima” per ogni capitolo ===
// (usa delegation per gestire anche elementi creati dinamicamente)
document.addEventListener("click", (e) => {
  const btn = e.target.closest(".btn-preview");
  if (!btn) return;

  const bookId = btn.dataset.bid;
  const chapterId = btn.dataset.cid;
  if (!bookId || !chapterId) return;

  const url = `${API_BASE_URL}/export/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}/export/pdf`;
  openPdfPreview(url);
});

/* ===== UI Tweaks Editor ===== */
function tweakChapterEditorUI() {
  const root =
    document.querySelector('[data-component="chapter-editor"]') ||
    document.querySelector('#editor-card') || document;
  if (!root) return;

  const chIdEl    = root.querySelector('#chapterIdInput');
  const chIdBlock = chIdEl?.closest('.field, .form-row, .card, label, div') || null;

  // Nasconde eventuale duplicato dell'ID capitolo
  const dupNode = Array.from(root.querySelectorAll('*')).find(el=>{
    if (!el || el === chIdEl) return false;
    if (chIdBlock && (el === chIdBlock || chIdBlock.contains(el))) return false;
    const t = (el.textContent || '').trim();
    return /^ch_\d{4}$/i.test(t);
  });
  if (dupNode) {
    const pill = dupNode.closest('.inline-hint, .badge, .pill, .tag, .field, .form-row, .card, label, div') || dupNode;
    pill.style.display = 'none';
    pill.setAttribute('aria-hidden', 'true');
  }

  let topicEl = root.querySelector('#topicInput');
  const langEl = root.querySelector('#languageInput');
  const chBlock = chIdEl?.closest('.field, .form-row, .card, label, div');
  if (!topicEl || !langEl || !chBlock) return;

  // Trasforma input in textarea se serve
  if (topicEl.tagName.toLowerCase() === 'input') {
    const ta = document.createElement('textarea');
    Array.from(topicEl.attributes).forEach(a => ta.setAttribute(a.name, a.value));
    ta.id = 'topicInput';
    ta.value = topicEl.value || '';
    topicEl.replaceWith(ta);
    topicEl = ta;
  }

  // Placeholder con esempi utili
  topicEl.rows = Math.max(4, Number(topicEl.rows || 0) || 4);
  const ex = [
    'Tono amichevole, target principianti; includi esempi pratici',
    'Stile narrativo: trasforma questi bullet in una storia coinvolgente',
    'Scrivi in 800-1000 parole; 4 sezioni con titoli H2 e checklist finale',
    'Inserisci 3 esempi reali e 2 errori comuni con soluzioni',
    'Adotta un tono accademico leggero; definizioni + riferimenti (senza link)'
  ].map(s => `• ${s}`).join('\n');

  topicEl.placeholder ||= 
    'Istruzioni per l’AI (tono, target, stile, obiettivi, riferimenti…)\n\n' +
    'Esempi:\n' + ex;

  // Blocchi contenitori
  const topicBlock = topicEl.closest('.field, .form-row, .card, label, div') || topicEl.parentElement;
  const langBlock  = langEl.closest('.field, .form-row, .card, label, div') || langEl.parentElement;

  // Griglia “Topic largo + Lingua compatta”
  let fields = chBlock.nextElementSibling;
  if (!(fields && fields.classList?.contains('fields'))) {
    fields = document.createElement('div');
    fields.className = 'fields';
    chBlock.parentNode.insertBefore(fields, chBlock.nextSibling);
  }
  if (topicBlock.parentNode !== fields) fields.appendChild(topicBlock);
  if (langBlock.parentNode  !== fields) fields.appendChild(langBlock);

  topicBlock.style.gridColumn = '1 / 2';
  topicBlock.style.width = '100%';
  langBlock.style.maxWidth = '220px';

  // Piccolo aiuto testuale sotto al topic
  if (!topicBlock.querySelector('[data-ai-help]')) {
    const help = document.createElement('div');
    help.setAttribute('data-ai-help','');
    help.className = 'muted';
    help.style.fontSize = '12px';
    help.style.marginTop = '4px';
    help.textContent = 'Suggerimento: più dettagli metti qui, più il capitolo sarà vicino a ciò che vuoi.';
    topicBlock.appendChild(help);
  }
ensureChapterTitleField();
} // ⟵ chiusura corretta della funzione

function ensureChapterTitleField(){
  const root =
    document.querySelector('[data-component="chapter-editor"]') ||
    document.querySelector('#editor-card') || document;

  if (!root) return;
  let titleEl = root.querySelector('#chapterTitleInput');
  if (titleEl) return; // già presente

  // crea il blocco titolo sopra al testo
  const ta = root.querySelector('#chapterText');
  const block = document.createElement('div');
  block.className = 'field';
  block.innerHTML = `
    <label for="chapterTitleInput" style="display:block;font-weight:600;margin-bottom:4px">Titolo capitolo</label>
    <input id="chapterTitleInput" type="text" placeholder="Es. Prefazione, Introduzione, Il viaggio inizia…" />
  `;
  if (ta?.parentNode) ta.parentNode.insertBefore(block, ta);
}

/* ===== Init ===== */
document.addEventListener("DOMContentLoaded", async ()=>{
  wireButtons();
  await pingBackend();
  await toggleLibrary(true);
  syncEditorButtonState();
});
