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

   // NEW — rileva "Indice/Sommario"
function isOutlineWanted(titleOrTopic = "") {
  const s = String(titleOrTopic).trim().toLowerCase();
  return /^(indice|sommario)$/.test(s) || /\b(indice|sommario)\b/.test(s);
}

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
// === Page format (persistenza) ===
const rememberPageFormat = (fmt)=>{ try{ localStorage.setItem("chapter_pdf_format", fmt||"6x9"); }catch{} };
const loadPageFormat     = ()=>{ try{ return localStorage.getItem("chapter_pdf_format") || "6x9"; }catch{ return "6x9"; } };
// === KDP prefs (persistenza) ===
const rememberCoverMode     = (m)=>{ try{ localStorage.setItem("book_cover_mode", m||"front"); }catch{} };
const loadCoverMode         = ()=>{ try{ return localStorage.getItem("book_cover_mode") || "front"; }catch{ return "front"; } };
// === Cover theme (persistenza) ===
const rememberCoverTheme = (s)=>{ try{ localStorage.setItem("cover_theme", s || "auto"); }catch{} };
const loadCoverTheme     = ()=>{ try{ return localStorage.getItem("cover_theme") || "auto"; }catch{ return "auto"; } };

const rememberBackcoverText = (t)=>{ try{ localStorage.setItem("book_backcover_text", t||""); }catch{} };
const loadBackcoverText     = ()=>{ try{ return localStorage.getItem("book_backcover_text") || ""; }catch{ return ""; } };

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
// NEW — SSE per generare l’Indice
function generateOutlineSSE({ topic = "Indice", language = "it", onLine, onDone, onError }) {
  const url = `${API_BASE_URL}/generate/chapter/sse`
            + `?topic=${encodeURIComponent(topic)}`
            + `&language=${encodeURIComponent(language)}`;

  const es = new EventSource(url);

  es.onmessage = (ev) => {
    if (typeof onLine === "function") onLine(ev.data);
  };
  es.addEventListener("done", () => {
    try { es.close(); } catch {}
    if (typeof onDone === "function") onDone();
  });
  es.addEventListener("error", (e) => {
    try { es.close(); } catch {}
    if (typeof onError === "function") onError(e);
  });

  return es;
}

/* ===== Capitoli / Editor ===== */
function nextChapterId(existing = []) {
  const nums = existing
    .map(c => String(c.id || ""))
    .map(id => (id.match(/ch_(\d{4})$/)?.[1]))
    .filter(Boolean)
    .map(n => parseInt(n, 10));
  const max = nums.length ? Math.max(...nums) : 0;
  const n = String(max + 1).padStart(4, "0");
  return `ch_${n}`;
}

async function showEditor(bookId) {
  if (!uiState.books.length) { await fetchBooks(); }

  const idToOpen = bookId || loadLastBook() || "";
  if (!idToOpen) return;

  rememberLastBook(idToOpen);
  $("#editor-card").style.display = "block";
  resetEditorForBook(idToOpen); // 👈 pulizia qui
  $("#bookIdInput").value = idToOpen;

  await loadBookMeta(idToOpen);
  await refreshChaptersList(idToOpen);
  tweakChapterEditorUI();

  if (!(uiState.chapters?.length)) {
    const nid = nextChapterId([]);
    $("#chapterIdInput").value = nid;
    uiState.currentChapterId = nid;
    $("#chapterText").focus();
  }

  startAutosave();
  syncEditorButtonState();
}

function closeEditor() {
  try { stopAutosave(); } catch {}
  const card = $("#editor-card");
  if (card) {
    card.style.display = "none";
    card.setAttribute("hidden", "true");
    card.setAttribute("aria-hidden", "true");
  }
  // reset stato editor per evitare autosave fantasma
  uiState.currentChapterId = "";
  uiState.lastSavedSnapshot = "";
  const ch  = $("#chapterIdInput");
  const ta  = $("#chapterText");
  const ttl = $("#chapterTitleInput");
  if (ch)  ch.value = "";
  if (ttl) ttl.value = "";
  if (ta)  ta.value = "";
}

// NEW — entrypoint unico per generare capitoli (con ramo speciale Indice)
async function handleGenerateChapter({ bookId, chapterId, title, topic, language = "it" }) {
  const editor = document.querySelector("#chapterText")
              || document.querySelector("#chapterTextarea")
              || document.querySelector("#contentInput");
  const wantOutline = isOutlineWanted(title || topic);

  if (wantOutline) {
    if (editor) editor.value = "";
    const lines = [];

    generateOutlineSSE({
      topic: title || topic || "Indice",
      language,
      onLine: (line) => { lines.push(line); if (editor) editor.value += line + "\n"; },
      onDone: async () => {
        const content = lines.join("\n").trim();
        await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
        }).catch(() => {});
        console.log("Indice generato e salvato");
      },
      onError: (e) => {
        console.error("Errore SSE:", e);
        alert("Errore nella generazione dell'indice. Riprova.");
      }
    });
    return; // interrompe la generazione “normale”
  }

  // 👉 qui continua la tua generazione normale (POST/stream) se non è un Indice
  // await generateChapterNormally({ bookId, chapterId, title, topic, language });
}

/* === Router click globale: UN SOLO listener === */
document.addEventListener("click", async (ev) => {
  const el = ev.target.closest("[data-action]");
  if (!el) return;
  const action = el.getAttribute("data-action");

  if (action === "generate") {
    if (uiState.isGenerating) return;      // evita doppi click
    uiState.isGenerating = true;
    try {
      const bookId    = $("#bookIdInput")?.value?.trim();
      const chapterId = $("#chapterIdInput")?.value?.trim();
      const title     = $("#chapterTitleInput")?.value?.trim() || "";
      const topic     = $("#topicInput")?.value?.trim() || title || "Indice";
      const language  = $("#languageInput")?.value || "it";

      if (!bookId || !chapterId) {
        alert("Seleziona un libro e un capitolo.");
        return;
      }
      await handleGenerateChapter({ bookId, chapterId, title, topic, language });
    } finally {
      uiState.isGenerating = false;
    }
    return;
  }

  // ...altri case già presenti (open/rename/delete/...) ...
});

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

   // --- Header sopra la lista capitoli (formato + KDP) ---
const header = document.createElement("div");
header.className = "row-right";
header.style.justifyContent = "flex-start";
header.style.alignItems = "center";
header.style.gap = "8px";
header.style.marginBottom = "8px";

const currentFmt   = (typeof loadPageFormat     === "function") ? loadPageFormat()     : "6x9";
const currentCover = (typeof loadCoverMode      === "function") ? loadCoverMode()      : "front";
const currentBack  = (typeof loadBackcoverText  === "function") ? loadBackcoverText()  : "";

header.innerHTML = `
  <label for="formatSelect" style="font-weight:600;">Formato:</label>
  <select id="formatSelect" class="input" style="margin-left:6px;">
    <option value="A4"  ${currentFmt==="A4"  ? "selected" : ""}>A4</option>
    <option value="6x9" ${currentFmt==="6x9" ? "selected" : ""}>6x9 (KDP)</option>
    <option value="5x8" ${currentFmt==="5x8" ? "selected" : ""}>5x8</option>
  </select>

  <span class="muted">·</span>

  <label for="coverModeSelect" style="font-weight:600;">Copertina:</label>
  <select id="coverModeSelect" class="input" style="margin-left:6px;">
    <option value="none"       ${currentCover==="none"       ? "selected" : ""}>Nessuna</option>
    <option value="front"      ${currentCover==="front"      ? "selected" : ""}>Solo fronte</option>
    <option value="front_back" ${currentCover==="front_back" ? "selected" : ""}>Fronte + retro</option>
  </select>

  <span class="muted">·</span>

  <label style="display:inline-flex;align-items:center;gap:6px;">
    <input type="checkbox" id="aiCover" ${ (localStorage.getItem("ai_cover")==="0") ? "" : "checked" } />
    Genera copertina AI
  </label>

  <span class="muted">·</span>

  <label for="themeSelect" style="font-weight:600;">Tema:</label>
  <select id="themeSelect" class="input" style="margin-left:6px;">
    <option value="auto"  ${(typeof loadCoverTheme==="function"?loadCoverTheme():"auto")==="auto"  ? "selected" : ""}>Auto</option>
    <option value="light" ${(typeof loadCoverTheme==="function"?loadCoverTheme():"auto")==="light" ? "selected" : ""}>Chiaro</option>
    <option value="dark"  ${(typeof loadCoverTheme==="function"?loadCoverTheme():"auto")==="dark"  ? "selected" : ""}>Scuro</option>
    <option value="blue"  ${(typeof loadCoverTheme==="function"?loadCoverTheme():"auto")==="blue"  ? "selected" : ""}>Blu</option>
    <option value="warm"  ${(typeof loadCoverTheme==="function"?loadCoverTheme():"auto")==="warm"  ? "selected" : ""}>Caldo</option>
  </select>

  <button id="btnGenCover" class="btn btn-secondary" style="margin-left:8px;">
    🖼️ Genera copertina (JPG)
  </button>

  <button id="toggleBackcover" class="btn btn-ghost" title="Mostra/nascondi quarta di copertina">✏️ Quarta</button>
`;
list.appendChild(header);

// --- Area testo "quarta di copertina" (collassabile) ---
const backWrap = document.createElement("div");
backWrap.id = "backcoverWrap";
backWrap.style.display = (currentCover === "front_back") ? "block" : "none";
backWrap.style.margin = "6px 0 10px 0";
backWrap.innerHTML = `
  <textarea id="backcoverText" rows="3" class="input" placeholder="Testo quarta di copertina…"
            style="width:100%;resize:vertical;">${escapeHtml(currentBack)}</textarea>
  <div class="row-right" style="justify-content:flex-start;gap:8px;margin-top:6px">
    <button id="saveKdpPrefs" class="btn btn-secondary">💾 Salva impostazioni KDP</button>
    <span class="muted">Verranno ricordate per i prossimi export.</span>
  </div>
`;
list.appendChild(backWrap);

// --- Event listeners ---

// Formato pagina
header.querySelector("#formatSelect")?.addEventListener("change",(e)=>{
  const v = e.target.value || "6x9";
  if (typeof rememberPageFormat === "function") rememberPageFormat(v);
  toast(`Formato: ${v}`);
});

// Modalità copertina
header.querySelector("#coverModeSelect")?.addEventListener("change",(e)=>{
  const m = e.target.value || "front";
  if (typeof rememberCoverMode === "function") rememberCoverMode(m);
  // mostra/nasconde la quarta
  const backWrapEl = $("#backcoverWrap");
  if (backWrapEl) backWrapEl.style.display = (m === "front_back") ? "block" : "none";
  toast(`Copertina: ${m === "none" ? "nessuna" : m === "front" ? "solo fronte" : "fronte+retro"}`);
});

// Switch "Genera copertina AI"
header.querySelector("#aiCover")?.addEventListener("change",(e)=>{
  const on = e.target.checked ? "1" : "0";
  try{ localStorage.setItem("ai_cover", on); }catch{}
  toast(`Copertina AI: ${on==="1" ? "attiva" : "spenta"}`);
});

// Tema copertina
header.querySelector("#themeSelect")?.addEventListener("change",(e)=>{
  const v = e.target.value || "auto";
  if (typeof rememberCoverTheme === "function") rememberCoverTheme(v);
  toast(`Tema copertina: ${v}`);
});

// Salva testo quarta
backWrap.querySelector("#saveKdpPrefs")?.addEventListener("click", ()=>{
  const t = backWrap.querySelector("#backcoverText")?.value || "";
  if (typeof rememberBackcoverText === "function") rememberBackcoverText(t.trim());
  toast("Impostazioni KDP salvate.");
});

// Genera copertina JPG (backend /generate/cover)
header.querySelector("#btnGenCover")?.addEventListener("click", async ()=>{
  try{
    await generateCoverFromCurrentBook();
  }catch(e){
    toast("Errore generazione copertina: " + (e?.message||e));
  }
});

// Mostra/nasconde area "quarta di copertina"
header.querySelector("#toggleBackcover")?.addEventListener("click", ()=>{
  const area  = document.getElementById("backcoverWrap");
  const btn   = header.querySelector("#toggleBackcover");
  const select= header.querySelector("#coverModeSelect");
  if (!area) return;

  const isHidden = area.style.display === "none" || getComputedStyle(area).display === "none";
  const show = isHidden;

  // mostra/nasconde
  area.style.display = show ? "block" : "none";

  // sync select (opzionale)
  if (select) {
    if (show && select.value !== "front_back")      select.value = "front_back";
    if (!show && select.value === "front_back")     select.value = "front";
  }

  // accessibilità + UX (opzionale)
  if (btn) {
    btn.setAttribute("aria-expanded", show ? "true" : "false");
    btn.textContent = show ? "🙈 Nascondi quarta" : "✏️ Quarta";
  }
  if (show) document.getElementById("backcoverText")?.focus();
});
   
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
  showMenuForButton(anchorBtn || document.body, EXPORT_FORMATS, async (fmtChoice)=>{
    const base = `${API_BASE_URL}/export/books/${encodeURIComponent(bookId)}/export`;
    try {
      if (fmtChoice === "kdp") {
        const trimSize   = localStorage.getItem("chapter_pdf_format") || "6x9";
        const coverMode  = localStorage.getItem("book_cover_mode")   || "front";
        const backText   = localStorage.getItem("book_backcover_text") || "";
        const aiFlag     = (localStorage.getItem("ai_cover") === "0") ? "0" : "1"; // default ON

        const url = `${base}/kdp`
          + `?size=${encodeURIComponent(trimSize)}`
          + `&cover_mode=${encodeURIComponent(coverMode)}`
          + (backText ? `&backcover_text=${encodeURIComponent(backText)}` : "")
          + `&ai_cover=${aiFlag}`;

        await fetchAndDownload(url, `book_${bookId}_kdp.zip`);
        return;
      }

      // pdf / md / txt
      const url  = `${base}/${fmtChoice}`;
      const name = `book_${bookId}.${fmtChoice}`;

      if (isSafariLike()) {
        await fetchAndDownload(url, name);
      } else {
        const win = window.open(url, "_blank", "noopener");
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

  const url = `${API_BASE_URL}/export/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chapterId)}/export/pdf?size=6x9&cover=false`;
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

// ======================================================
// 📘 Genera copertina (usa endpoint senza /api/v1)
// ======================================================
async function generateCoverFromCurrentBook() {
  const bookId = uiState.currentBookId || $("#bookIdInput")?.value?.trim();
  if (!bookId) {
    toast("Apri un libro prima!");
    return;
  }

  // Carica titolo/autore dalla libreria o dai campi
  const book = (uiState.books || []).find(b => b?.id === bookId);
  const title  = String(book?.title  || loadLastBookTitle()  || "Senza titolo");
  const author = String(book?.author || loadLastAuthor()     || "Autore sconosciuto");

  // Formato e tema salvati
  const size  = (typeof loadPageFormat  === "function") ? loadPageFormat()  : "6x9";
  const theme = (typeof loadCoverTheme  === "function") ? loadCoverTheme()  : "dark";

  // === Base URL corretta per le cover ===
  const COVER_BASE_URL = API_BASE_URL.replace(/\/api\/v1$/, "");

  // === Costruisci URL backend ===
  const url = `${COVER_BASE_URL}/generate/cover`
            + `?title=${encodeURIComponent(title)}`
            + `&author=${encodeURIComponent(author)}`
            + `&style=${encodeURIComponent(theme)}`
            + `&size=${encodeURIComponent(size)}`;

  // === Scarica la JPG ===
  await fetchAndDownload(url, `cover_${bookId}_${size}_${theme}.jpg`);
  toast("Copertina generata!");
}

/* ===== Init ===== */
document.addEventListener("DOMContentLoaded", async ()=>{
  wireButtons();
  await pingBackend();
  await toggleLibrary(true);
  syncEditorButtonState();
});

/* =========================================================
 * EccomiBook — UX2 Add-on (single-file, opt-in)
 * UI nuova: Indice · AI Autocompose · Self-compose
 * ========================================================= */

/* === Markup della UI UX2 === */
const UX2_HTML = `
<div id="ux2">
  <div class="app">
    <div class="topbar">
      <div class="brand"><span class="dot"></span> EccomiBook</div>
      <div class="mode-tabs">
        <button class="tab active" data-mode="indice">Indice</button>
        <button class="tab" data-mode="autocompose">AI Autocompose Book</button>
        <button class="tab" data-mode="self">Scrivi il titolo…</button>
      </div>
      <span class="pill">Libro: <span id="ux2BookName">—</span></span>
      <div class="spacer"></div>
      <div class="row start"><span class="led ok"></span><span class="muted mono">UX2</span></div>
    </div>

    <button class="tab" id="ux2LibraryBtn" style="margin:10px 14px 0">📚 Libreria</button>

    <div class="main">
      <!-- Indice -->
      <section class="panel">
        <h3>Indice</h3>
        <div class="body">
          <div class="row start" style="gap:8px;margin-bottom:10px">
            <button class="btn secondary" id="ux2GenIndex">Genera Indice</button>
            <button class="btn ghost" id="ux2LockAll">Blocca tutti</button>
            <button class="btn ghost" id="ux2MarkAll">Seleziona comporre</button>
          </div>
          <div id="ux2Tree"></div>
        </div>
        <div class="actions-bar">
          <button class="btn ghost" data-preset="acc">Preset: Accademico</button>
          <button class="btn ghost" data-preset="nar">Preset: Narrativo</button>
          <button class="btn ghost" data-preset="man">Preset: Manuale</button>
        </div>
      </section>

      <!-- Centro -->
      <section class="panel">
        <h3 id="ux2CenterTitle">Index Builder</h3>
        <div class="body">
          <!-- MODE: Indice -->
          <div id="ux2ModeIndice">
            <div class="row start" style="gap:8px;margin-bottom:8px;flex-wrap:wrap">
              <input class="input" id="ux2IndexTitle" placeholder="Titolo libro" style="max-width:420px">
              <select class="input" id="ux2Parts" style="max-width:200px">
                <option value="with">Con Parti</option>
                <option value="no">Solo capitoli</option>
              </select>
              <select class="input" id="ux2IndexMode" style="max-width:260px">
                <option value="respect">Respect capitoli esistenti</option>
                <option value="fresh">Fresh da zero</option>
                <option value="blurb">Blurb da sinossi</option>
              </select>
            </div>
            <textarea id="ux2Blurb" class="input mono" rows="6" placeholder="Sinossi / scopo / note editoriali (per modalità Blurb)…"></textarea>
            <div style="display:flex;gap:8px;margin:10px 0">
              <button class="btn" id="ux2PreviewIndex">Anteprima</button>
              <button class="btn ghost" id="ux2InsertIndex">Inserisci come capitolo 'Indice'</button>
            </div>
            <pre id="ux2IndexPreview" class="mono" style="white-space:pre-wrap;background:#0d1019;border:1px solid #232a3a;padding:10px;border-radius:10px;min-height:120px"></pre>
          </div>

          <!-- MODE: Autocompose -->
          <div id="ux2ModeAuto" style="display:none">
            <div class="row start" style="gap:8px;flex-wrap:wrap;margin-bottom:8px">
              <select class="input" id="ux2Style" style="max-width:210px">
                <option value="acc">Stile: Accademico</option>
                <option value="nar">Stile: Narrativo</option>
                <option value="man">Stile: Manuale</option>
              </select>
              <select class="input" id="ux2Tone" style="max-width:210px">
                <option value="neutro">Tono: Neutro</option>
                <option value="amichevole">Tono: Amichevole</option>
                <option value="tecnico">Tono: Tecnico</option>
              </select>
            </div>
            <div class="row start" style="gap:8px;margin:8px 0">
              <button class="btn" id="ux2Compose">Autocompose selezionati</button>
              <button class="btn ghost" id="ux2Pause">Pausa</button>
              <button class="btn ghost" id="ux2Resume">Riprendi</button>
            </div>
            <div>
              <div class="progress"><div id="ux2BookBar" class="bar" style="width:0%"></div></div>
              <div class="row"><small class="muted">Completato</small><small id="ux2BookPct">0%</small></div>
            </div>
            <div style="margin-top:10px">
              <h4 class="muted" style="margin:0 0 6px">Coda lavori</h4>
              <div id="ux2Jobs"></div>
            </div>
          </div>

          <!-- MODE: Self -->
          <div id="ux2ModeSelf" style="display:none">
            <input class="input" id="ux2ChapterTitle" placeholder="Titolo capitolo…" style="margin-bottom:8px">
            <textarea class="input mono" id="ux2Editor" placeholder="Scrivi qui il contenuto…"></textarea>
            <div class="row" style="margin-top:8px">
              <div>
                <button class="btn ghost" id="ux2Expand">Espandi</button>
                <button class="btn ghost" id="ux2Rewrite">Riformula</button>
                <button class="btn ghost" id="ux2Summ">Sintetizza</button>
              </div>
              <div class="muted">Autosave • ⌘S</div>
            </div>
          </div>
        </div>
        <div class="actions-bar">
          <button class="btn ghost" id="ux2ExportPdf">Esporta PDF</button>
          <button class="btn ghost" id="ux2ExportMd">Esporta MD</button>
          <button class="btn" id="ux2ExportKdp">Esporta KDP ZIP</button>
        </div>
      </section>

      <!-- Destra -->
      <aside class="panel">
        <h3>Profilo & Copertina</h3>
        <div class="body">
          <div style="border:1px dashed #232a3a;border-radius:12px;padding:10px;margin-bottom:10px">
            <label class="muted">Scopo del libro</label>
            <textarea id="ux2Scope" class="input" rows="2" placeholder="Es. fornire basi teoriche e pratiche…"></textarea>
            <label class="muted" style="margin-top:6px;display:block">Metodologia / Note</label>
            <textarea id="ux2Meth" class="input" rows="2" placeholder="Es. approccio graduale, esempi, esercizi…"></textarea>
          </div>
          <div style="border:1px dashed #232a3a;border-radius:12px;padding:10px">
            <div class="row start" style="gap:8px">
              <select class="input" id="ux2Trim" style="max-width:140px">
                <option>6x9</option><option>5x8</option><option>A4</option>
              </select>
              <select class="input" id="ux2CoverMode" style="max-width:160px">
                <option value="front">Solo fronte</option>
                <option value="front_back">Fronte + retro</option>
              </select>
            </div>
            <button class="btn ghost" id="ux2GenCover" style="margin-top:8px">Genera copertina (JPG)</button>
          </div>
        </div>
      </aside>
    </div>
  </div>
</div>`;

/* ---- Feature flag ---- */
const UX2_ENABLED = (() => {
  try {
    const q = new URLSearchParams(location.search);
    if (q.get("ux2") === "1") { localStorage.setItem("ux2", "1"); }
    if (q.get("ux2") === "0") { localStorage.setItem("ux2", "0"); }
    return (localStorage.getItem("ux2") === "1");
  } catch { return false; }
})();

/* ---- Mount only if enabled ---- */
if (UX2_ENABLED) {
  console.log("[UX2] enabled");

  // 1) CSS base
  const ux2Css = `
  #ux2{position:relative; z-index:5; color:#e9edf5; font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
  #ux2, #ux2 *{box-sizing:border-box}
  #ux2 .app{display:grid;grid-template-rows:58px auto;min-height:100vh;background:linear-gradient(180deg,#0b0e13,#0f1115)}
  #ux2 .topbar{display:flex;align-items:center;gap:16px;padding:10px 16px;background:#151924;border-bottom:1px solid #232a3a;position:sticky;top:0;z-index:10}
  #ux2 .brand{display:flex;align-items:center;gap:10px;font-weight:700;letter-spacing:.2px}
  #ux2 .brand .dot{width:10px;height:10px;border-radius:50%;background:#ff2244;box-shadow:0 0 0 3px rgba(255,34,68,.25)}
  #ux2 .mode-tabs{display:flex;gap:6px;margin-left:8px}
  #ux2 .tab{border:1px solid #232a3a;background:#0f1320;color:#cbd5e1;padding:8px 12px;border-radius:10px;cursor:pointer}
  #ux2 .tab.active{border-color:#ff2244;color:#fff;box-shadow:0 0 0 2px rgba(255,34,68,.2) inset}
  #ux2 .spacer{flex:1}
  #ux2 .led{width:10px;height:10px;border-radius:50%;background:#3a3f52;margin-right:6px}
  #ux2 .led.ok{background:#25d366;box-shadow:0 0 0 4px rgba(37,211,102,.2)}
  #ux2 .pill{padding:6px 10px;border-radius:999px;background:#1a2130;border:1px solid #232a3a;color:#cdd6e6}
  #ux2 .btn{background:#ff2244;color:#fff;border:0;padding:8px 12px;border-radius:10px;cursor:pointer;font-weight:600}
  #ux2 .btn.secondary{background:#2d6bff}
  #ux2 .btn.ghost{background:transparent;border:1px solid #232a3a;color:#cbd5e1}
  #ux2 .main{display:grid;gap:14px;padding:14px;grid-template-columns:320px 1fr 360px}
  #ux2 .panel{background:#151924;border:1px solid #232a3a;border-radius:14px;overflow:hidden;display:flex;flex-direction:column;min-height:0}
  #ux2 .panel h3{margin:0;padding:12px 14px;border-bottom:1px solid #232a3a;font-size:13px;text-transform:uppercase;letter-spacing:.4px;color:#b8c2d9}
  #ux2 .panel .body{padding:10px 12px;overflow:auto;min-height:0}
  #ux2 .node{background:#0f1320;border:1px solid #232a3a;border-radius:10px;padding:10px;margin-bottom:8px}
  #ux2 .row{display:flex;align-items:center;gap:8px;justify-content:space-between}
  #ux2 .row.start{justify-content:flex-start}
  #ux2 .title{flex:1;font-weight:600}
  #ux2 .chip{background:#1a2130;border:1px solid #232a3a;color:#cbd5e1;padding:3px 8px;border-radius:999px;font-size:12px}
  #ux2 .muted{color:#8a93a6}
  #ux2 .actions-bar{display:flex;gap:8px;padding:10px;background:#0d1019;border-top:1px solid #232a3a}
  #ux2 .input, #ux2 textarea, #ux2 select{background:#0e1220;color:#e9edf5;border:1px solid #232a3a;border-radius:10px;padding:8px 10px;width:100%}
  #ux2 textarea{min-height:200px;resize:vertical}
  #ux2 .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px}
  #ux2 .progress{height:8px;background:#0b0e16;border:1px solid #232a3a;border-radius:999px;overflow:hidden}
  #ux2 .bar{height:100%;width:0%;background:linear-gradient(90deg,#ff2244,#ff5f7a)}
  @media (max-width: 1024px){ #ux2 .main{grid-template-columns:1fr} }
  `;
  const s = document.createElement("style");
  s.textContent = ux2Css;
  document.head.appendChild(s);

  // 1b) Fix layout aggiuntivi
  (()=>{
    const fix = document.createElement("style");
    fix.textContent = `
      #ux2 .node > .row:first-child{display:grid;grid-template-columns:1fr 28px 92px;align-items:center;gap:8px}
      #ux2 .node > .row:first-child label.row{min-width:0;gap:8px}
      #ux2 .node .title{white-space:normal;word-break:normal;overflow-wrap:break-word;hyphens:auto;-webkit-hyphens:auto;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:3;max-height:3.9em;font-weight:600;line-height:1.2}
      #ux2 .node [data-lock]{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:6px;border:1px solid #232a3a;background:#0f1320;color:#cbd5e1;user-select:none}
      #ux2 .node > .row:first-child > .row{justify-content:flex-end;gap:6px}
      #ux2 .node > .row:first-child > .row .btn{width:28px;height:28px;padding:0;display:inline-flex;align-items:center;justify-content:center;border-radius:6px;line-height:1;font-size:12px;border:1px solid #232a3a;background:#0f1320;color:#cbd5e1}
      #ux2 .node > .row:last-child{margin-top:6px;color:#8a93a6;font-size:12px;display:flex;justify-content:space-between}
      #ux2 .main{grid-template-columns:360px 1fr 340px}
      @media (max-width:1024px){ #ux2 .main{grid-template-columns:1fr} }
      #ux2 .node{contain:layout paint;transform:translateZ(0)}
      #ux2 .panel .body{-webkit-overflow-scrolling:touch}
      #ux2 *{-webkit-tap-highlight-color:transparent}
    `;
    document.head.appendChild(fix);
  })();

  // 2) Mount HTML
  const container = document.createElement("div");
  container.innerHTML = UX2_HTML;
  document.body.innerHTML = "";
  const ux2Root = container.firstElementChild;
  document.body.appendChild(ux2Root);

  // Utils
  function escapeHtml(s){
    return String(s)
      .replaceAll("&","&amp;")
      .replaceAll("<","&lt;")
      .replaceAll(">","&gt;")
      .replaceAll('"',"&quot;")
      .replaceAll("'","&#39;");
  }
  function escapeAttr(s){ return escapeHtml(s).replaceAll("\n"," "); }

  // 3) Libreria (pulsante)
  (() => {
    const API = (window.VITE_API_BASE_URL) || "https://eccomibook-backend.onrender.com/api/v1";
    const ux2LibBtn = ux2Root.querySelector("#ux2LibraryBtn");
    if (!ux2LibBtn) return;
    ux2LibBtn.addEventListener("click", async ()=>{
      try {
        const res = await fetch(`${API}/books`, { method:"GET" });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data  = await res.json();
        const books = Array.isArray(data) ? data : (data.books || []);
        alert(
          books.length
            ? books.map(b => `📘 ${(b.title||"Senza titolo")} (${(b.id||b._id||b.book_id||"——").toString().slice(0,6)}…)`).join("\n")
            : "Nessun libro presente."
        );
      } catch (err) {
        console.error("[UX2] Libreria errore:", err);
        alert("Errore nel caricamento della libreria");
      }
    });
  })();

  // 4) Preset struttura
  const presetAcc = [
    { id:"1",   title:"Indice", lock:true },
    { id:"1.1", title:"Scopo del libro" },
    { id:"1.2", title:"Struttura del libro" },
    { id:"1.3", title:"Metodologia" },
    { id:"2",   title:"Capitolo 1: Fondamenti" },
    { id:"2.1", title:"Definizioni chiave" },
    { id:"2.2", title:"Teorie di base" },
    { id:"2.3", title:"Applicazioni pratiche" },
    { id:"3",   title:"Capitolo 2: Approfondimenti" },
    { id:"3.1", title:"Analisi avanzata" },
    { id:"3.2", title:"Studi di caso" },
    { id:"3.3", title:"Discussione critica" },
    { id:"4",   title:"Capitolo 3: Prospettive future" },
    { id:"4.1", title:"Tendenze emergenti" },
    { id:"4.2", title:"Sfide e opportunità" },
    { id:"4.3", title:"Conclusioni" },
    { id:"5",   title:"Appendici" },
    { id:"5.1", title:"Glossario" },
    { id:"5.2", title:"Riferimenti" },
    { id:"5.3", title:"Ringraziamenti" },
  ];
  const presetNar = [
    { id:"0", title:"Indice", lock:true },
    { id:"1", title:"Prologo" },
    { id:"2", title:"Atto I — L’innesco" },
    { id:"3", title:"Atto II — Il conflitto" },
    { id:"4", title:"Atto III — La risoluzione" },
    { id:"5", title:"Epilogo" },
  ];
  const presetMan = [
    { id:"0", title:"Indice", lock:true },
    { id:"1", title:"Introduzione" },
    { id:"2", title:"Setup e prerequisiti" },
    { id:"3", title:"Procedure passo-passo" },
    { id:"4", title:"Checklist finali" },
    { id:"5", title:"FAQ + Troubleshooting" },
  ];

  const ux2 = {
    state: { mode:"indice", tree:[...presetAcc], paused:false, composing:false, bookPct:0 },
    q:  (s, r=document) => (r||document).querySelector(s),
    qa: (s, r=document) => Array.from((r||document).querySelectorAll(s)),
  };

  // 5) Tabs
  ux2.qa("#ux2 .tab").forEach(t=>{
    t.addEventListener("click", ()=>{
      ux2.qa("#ux2 .tab").forEach(x=>x.classList.remove("active"));
      t.classList.add("active");
      ux2.state.mode = t.dataset.mode;
      ux2.q("#ux2CenterTitle").textContent =
        ux2.state.mode==="indice" ? "Index Builder" :
        ux2.state.mode==="autocompose" ? "AI Autocompose" : "Editor (Self-compose)";
      ux2.q("#ux2ModeIndice").style.display = ux2.state.mode==="indice" ? "block" : "none";
      ux2.q("#ux2ModeAuto").style.display   = ux2.state.mode==="autocompose" ? "block" : "none";
      ux2.q("#ux2ModeSelf").style.display   = ux2.state.mode==="self" ? "block" : "none";
    });
  });

  // 6) Render albero
  function renderTree(){
    const host = ux2.q("#ux2Tree"); host.innerHTML = "";
    ux2.state.tree.forEach(n=>{
      const row = document.createElement("div");
      row.className = "node";
      row.innerHTML = `
        <div class="row">
          <label class="row start" style="gap:8px;flex:1">
            <input type="checkbox" ${n.do?"checked":""} data-id="${n.id}">
            <span class="chip mono">${n.id}</span>
            <span class="title" title="${escapeAttr(n.title||'')}">${escapeHtml(n.title||"")}</span>
          </label>
          <span class="chip ${n.lock?"muted":""}" data-lock="${n.id}" title="Blocca/sblocca">🔒</span>
          <div class="row" style="gap:6px">
            <button class="btn ghost" data-up="${n.id}">↑</button>
            <button class="btn ghost" data-down="${n.id}">↓</button>
            <button class="btn ghost" data-del="${n.id}">✕</button>
          </div>
        </div>
        <div class="row" style="margin-top:6px">
          <small class="muted">${n.lock ? "bloccato (manuale)" : (n.do ? "da comporre" : "—")}</small>
          <small class="muted">stato: <span class="mono">${n.status||"vuoto"}</span></small>
        </div>`;
      host.appendChild(row);
    });
  }
  renderTree();

  // 7) Interazioni albero
  ux2.q("#ux2Tree").addEventListener("change",(e)=>{
    if(e.target.matches("input[type=checkbox]")){
      const id = e.target.getAttribute("data-id");
      const node = ux2.state.tree.find(x=>x.id===id);
      if(node) node.do = e.target.checked;
      updateJobsPreview();
    }
  });
  ux2.q("#ux2Tree").addEventListener("click",(e)=>{
    const up   = e.target.getAttribute("data-up");
    const down = e.target.getAttribute("data-down");
    const del  = e.target.getAttribute("data-del");
    const lock = e.target.closest?.("[data-lock]")?.getAttribute("data-lock");
    if(up)   moveNode(up, -1);
    if(down) moveNode(down, +1);
    if(del){ ux2.state.tree = ux2.state.tree.filter(x=>x.id!==del); renderTree(); updateJobsPreview(); }
    if(lock){
      const node = ux2.state.tree.find(x=>x.id===lock);
      if(node){ node.lock = !node.lock; renderTree(); }
    }
  });
  function moveNode(id, delta){
    const i = ux2.state.tree.findIndex(x=>x.id===id);
    if(i<0) return;
    const j = Math.max(0, Math.min(ux2.state.tree.length-1, i+delta));
    if(i===j) return;
    const [n] = ux2.state.tree.splice(i,1);
    ux2.state.tree.splice(j,0,n);
    renderTree(); updateJobsPreview();
  }

  // 8) Preset
  ux2.qa('[data-preset]').forEach(b=>{
    b.addEventListener("click", ()=>{
      const p = b.getAttribute("data-preset");
      ux2.state.tree = p==="nar" ? [...presetNar] : p==="man" ? [...presetMan] : [...presetAcc];
      renderTree(); updateJobsPreview();
    });
  });
  ux2.q("#ux2LockAll").addEventListener("click", ()=>{ ux2.state.tree.forEach(n=>n.lock=true); renderTree(); });
  ux2.q("#ux2MarkAll").addEventListener("click", ()=>{ ux2.state.tree.forEach(n=>n.do=true); renderTree(); updateJobsPreview(); });

  // 9) Preview indice
  function buildIndexMarkdown(){
    const withParts = ux2.q("#ux2Parts").value === "with";
    const lines = [];
    lines.push(`**Prefazione**`);
    lines.push(`**Introduzione**`);
    let part = 1;
    ux2.state.tree.forEach(n=>{
      if(n.id==="1" || (n.title||"").trim().toLowerCase()==="indice") return;
      const isMain = !String(n.id).includes(".");
      if(withParts && isMain){ lines.push(\`\\n## Parte \${part} — \${n.title}\`); part++; }
      else if(isMain){ lines.push(\`\\n\${n.id}. \${n.title}\`); }
      else { lines.push(\`\${n.id}. \${n.title}\`); }
    });
    lines.push(`\n**Ringraziamenti**`);
    lines.push(`\n**Note bibliografiche**`);
    return lines.join("\n");
  }
  ux2.q("#ux2PreviewIndex").addEventListener("click", ()=>{
    ux2.q("#ux2IndexPreview").textContent = buildIndexMarkdown();
  });

  // 10) Genera/Inserisci Indice
  ux2.q("#ux2GenIndex").addEventListener("click", ()=>{
    ux2.qa("#ux2 .tab").find(t=>t.dataset.mode==="indice")?.click();
    ux2.q("#ux2PreviewIndex").click();
  });
  ux2.q("#ux2InsertIndex").addEventListener("click", async ()=>{
    try{
      const bookId    = (window.uiState?.currentBookId) || document.querySelector("#bookIdInput")?.value?.trim();
      const chapterId = (window.uiState?.currentChapterId) || document.querySelector("#chapterIdInput")?.value?.trim() || (typeof window.nextChapterId==="function" ? window.nextChapterId(window.uiState?.chapters||[]) : "ch_0001");
      const title     = "Indice";
      const topic     = buildIndexMarkdown();

      if (!bookId) { if (window.toast) window.toast("Apri un libro prima"); return; }

      var b = document.querySelector("#bookIdInput");    if (b) b.value = bookId;
      var c = document.querySelector("#chapterIdInput"); if (c) c.value = chapterId || "";
      var t = document.querySelector("#chapterTitleInput"); if (t) t.value = title;

      if (typeof window.handleGenerateChapter === "function") {
        await window.handleGenerateChapter({ bookId, chapterId, title, topic, language: window.uiState?.currentLanguage||"it" });
      }
      if (window.toast) window.toast("✅ Indice generato/salvato");
      if (typeof window.refreshChaptersList === "function") await window.refreshChaptersList(bookId);
    }catch(e){ if (window.toast) window.toast("Errore inserimento indice: " + (e?.message||e)); }
  });

  // 11) Autocompose queue
  function updateJobsPreview(){
  const todo = ux2.state.tree.filter(n=>n.do && !n.lock);
  jobsEl.innerHTML = todo.map(n=>{
    const id    = String(n?.id ?? "");
    const title = escapeHtml(n?.title ?? "");
    const st    = (n && n.status) ? String(n.status) : "in coda";
    const pct   = (n && typeof n.pct === "number") ? n.pct : 0;

    return (
      '<div class="row" style="gap:8px;margin-bottom:6px">' +
        '<div style="flex:1">' +
          '<div><strong>'+id+'</strong> — '+title+'</div>' +
          '<div class="muted mono">'+st+'</div>' +
        '</div>' +
        '<div class="progress" style="width:160px">' +
          '<div class="bar" style="width:'+pct+'%"></div>' +
        '</div>' +
      '</div>'
    );
  }).join("");
}

  updateJobsPreview();

  ux2.q("#ux2Compose").addEventListener("click", async ()=>{
    const bookId = (window.uiState?.currentBookId) || document.querySelector("#bookIdInput")?.value?.trim();
    if (!bookId) { if (window.toast) window.toast("Apri un libro prima"); return; }
    const todo = ux2.state.tree.filter(n=>n.do && !n.lock);
    if (!todo.length) { if (window.toast) window.toast("Seleziona nodi 'da comporre'"); return; }

    ux2.state.composing = true; ux2.state.paused = false; ux2.state.bookPct = 0;
    for (const n of todo) {
      if (ux2.state.paused) break;
      let chId = window.uiState?.chapters?.find(c=> (c.title||"").trim()===n.title)?.id;
      if (!chId && typeof window.apiCreateChapter === "function") {
        try {
          const res = await window.apiCreateChapter(bookId, { title:n.title, content:"", language: window.uiState?.currentLanguage||"it" });
          chId = res?.chapter?.id;
          if (typeof window.refreshChaptersList === "function") await window.refreshChaptersList(bookId);
        } catch (e) { console.warn("createChapter fail", e); continue; }
      }
      var b = document.querySelector("#bookIdInput");    if (b) b.value = bookId;
      var c = document.querySelector("#chapterIdInput"); if (c) c.value = chId || "";

      n.status = "generazione…"; n.pct = 10; updateJobsPreview();
      try{
        if (typeof window.generateWithAI_auto === "function") await window.generateWithAI_auto();
        n.status = "composto"; n.pct = 100; updateJobsPreview();
      }catch(e){
        n.status = "errore"; n.pct = 0; updateJobsPreview();
      }
      ux2.state.bookPct = Math.min(100, Math.floor(((todo.filter(x=>x.pct===100).length)/todo.length)*100));
      ux2.q("#ux2BookBar").style.width = ux2.state.bookPct + "%";
      ux2.q("#ux2BookPct").textContent = ux2.state.bookPct + "%";
    }
    ux2.state.composing = false;
  });
  ux2.q("#ux2Pause").addEventListener("click", ()=>{ ux2.state.paused = true; });
  ux2.q("#ux2Resume").addEventListener("click", ()=>{ ux2.state.paused = false; });

  // 12) Self-compose mock
  ux2.q("#ux2Expand") .addEventListener("click", ()=> window.toast && window.toast("Mock: Espandi (hook pronto)"));
  ux2.q("#ux2Rewrite").addEventListener("click", ()=> window.toast && window.toast("Mock: Riformula (hook pronto)"));
  ux2.q("#ux2Summ")   .addEventListener("click", ()=> window.toast && window.toast("Mock: Sintetizza (hook pronto)"));

  // 13) Export & Cover
  ux2.q("#ux2ExportPdf").addEventListener("click", ()=> window.exportBook && window.exportBook(window.uiState?.currentBookId, null, "pdf"));
  ux2.q("#ux2ExportMd") .addEventListener("click", ()=> window.exportBook && window.exportBook(window.uiState?.currentBookId, null, "md"));
  ux2.q("#ux2ExportKdp").addEventListener("click", ()=> window.exportBook && window.exportBook(window.uiState?.currentBookId, null, "kdp"));
  ux2.q("#ux2GenCover") .addEventListener("click", ()=> window.generateCoverFromCurrentBook && window.generateCoverFromCurrentBook());

  // 14) Nome libro
  try{
    const cur = window.uiState?.books?.find(b=> (b.id||b.book_id) === (window.uiState?.currentBookId||document.querySelector("#bookIdInput")?.value?.trim()));
    ux2.q("#ux2BookName").textContent = cur?.title || "—";
  }catch{ ux2.q("#ux2BookName").textContent = "—"; }
}

/* ===== Fine UX2 Add-on ===== */

