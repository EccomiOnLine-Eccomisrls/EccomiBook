/* =========================================================
 * EccomiBook — Frontend vanilla (Vite)
 * main.js (completo, “concreto”)
 * ========================================================= */

/* ───────────── Config ───────────── */

// URL backend: da ENV Vite (Render) oppure fallback pubblico
const API_BASE_URL =
  (import.meta?.env?.VITE_API_BASE_URL) ||
  window.VITE_API_BASE_URL ||
  "https://eccomibook-backend.onrender.com";

// (per ora l’editor capitolo resta “demo” sul PUT; quando abiliti l’endpoint, metti a false)
window.USE_DEMO_EDITOR = true;

/* ───────────── Util ───────────── */

const $  = (sel) => document.querySelector(sel);
const setText = (id, txt) => { const el = document.getElementById(id); if (el) el.textContent = txt; };

function getApiKey() {
  try { return localStorage.getItem("eccomibook_api_key") || ""; } catch { return ""; }
}
function setApiKey(k) {
  try { localStorage.setItem("eccomibook_api_key", k || ""); } catch {}
}

/* ───────────── Header: stato backend ───────────── */

async function pingBackend() {
  const el = document.getElementById("backend-status");
  if (!el) return;

  setText("backend-status", "Backend: verifico…");
  try {
    const r = await fetch(`${API_BASE_URL}/health`, { method: "GET" });
    setText("backend-status", r.ok ? "Backend: OK" : `Backend: errore ${r.status}`);
  } catch {
    setText("backend-status", "Backend: non raggiungibile");
  }

  // mini debug: URL API
  const dbg = document.createElement("div");
  dbg.className = "debug-url";
  dbg.innerHTML = `API: <a href="${API_BASE_URL}" target="_blank" rel="noreferrer">${API_BASE_URL}</a>`;
  el.appendChild(dbg);
}

/* ───────────── Azioni UI ───────────── */

function askApiKey() {
  const cur = getApiKey();
  const val = prompt("Imposta la tua x-api-key:", cur || "demo_key_owner");
  if (val != null) {
    setApiKey(val.trim());
    alert("API key salvata.");
  }
}

async function createBookSimple() {
  const API = API_BASE_URL;
  const KEY = getApiKey() || "demo_key_owner";

  // 1) test chiave
  try {
    const who = await fetch(`${API}/_whoami`, { headers: { "x-api-key": KEY } });
    if (!who.ok) {
      const body = await who.text().catch(()=>"");
      alert(`❌ _whoami -> ${who.status}\n${body}`);
      return;
    }
  } catch (e) {
    alert(`❌ _whoami: errore di rete (${e?.message || e})\nURL: ${API}/_whoami`);
    return;
  }

  // 2) titolo
  const title = prompt("Titolo del libro:", "Manuale EccomiBook");
  if (!title) return;

  // 3) crea libro
  try {
    const res = await fetch(`${API}/books/create`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": KEY
      },
      body: JSON.stringify({
        title,
        author: "EccomiBook",
        language: "it",
        chapters: []
      })
    });

    if (!res.ok) {
      let msg = "";
      try { msg = JSON.stringify(await res.json()); }
      catch { msg = await res.text(); }
      alert(`❌ /books/create -> ${res.status}\n${msg}`);
      return;
    }

    const data = await res.json();
    try { localStorage.setItem("last_book_id", data.book_id); } catch {}
    alert(`✅ Libro creato!\nID: ${data.book_id}\nTitolo: ${data.title}`);
  } catch (e) {
    alert(`❌ Errore di rete: ${e?.message || e}\nURL: ${API}/books/create`);
  }
}

function openLibrary() {
  // Placeholder: quando aggiungiamo GET /books lo colleghiamo
  const last = (()=>{ try { return localStorage.getItem("last_book_id") || "(nessuno)"; } catch { return "(nessuno)"; }})();
  alert(`Libreria (demo): ultimo ID salvato = ${last}\n(Collegheremo GET /books per l’elenco reale.)`);
}

function openEditor() {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "block";

  // riempi campi se vuoti
  const b = $("#bookIdInput"), c = $("#chapterIdInput"), t = $("#chapterText");
  if (b && !b.value) b.value = (localStorage.getItem("last_book_id") || "book_il-mio-libro_xxxxxx");
  if (c && !c.value) c.value = "ch_0001";
  if (t && !t.value) t.value = "Scrivi qui il contenuto del capitolo...";
}

function closeEditor() {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "none";
}

async function saveChapter() {
  const bookId = $("#bookIdInput")?.value?.trim();
  const chId   = $("#chapterIdInput")?.value?.trim();
  const text   = $("#chapterText")?.value ?? "";

  if (!bookId || !chId) { alert("Inserisci ID libro e ID capitolo."); return; }

  if (window.USE_DEMO_EDITOR) {
    alert(`(DEMO) Salvataggio simulato.\nBook: ${bookId}\nChapter: ${chId}\nTesto: ${text.slice(0,200)}${text.length>200?"...":""}`);
    return;
  }

  // quando abiliterai il PUT backend, decommenta qui sotto:
  /*
  try {
    const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chId)}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": getApiKey() || "demo_key_owner"
      },
      body: JSON.stringify({ content: text })
    });
    if (!res.ok) {
      let msg = "";
      try { msg = JSON.stringify(await res.json()); }
      catch { msg = await res.text(); }
      alert(`❌ PUT capitolo -> ${res.status}\n${msg}`);
      return;
    }
    alert("✅ Capitolo aggiornato!");
  } catch(e) {
    alert(`❌ Errore di rete PUT: ${e?.message || e}`);
  }
  */
}

/* ───────────── Hook UI & Init ───────────── */

function wireButtons() {
  $("#btn-api-key")?.addEventListener("click", askApiKey);
  $("#btn-new-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", openLibrary);
  $("#btn-editor")?.addEventListener("click", openEditor);

  $("#btn-ed-save")?.addEventListener("click", saveChapter);
  $("#btn-ed-close")?.addEventListener("click", closeEditor);
}

document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();
  const badge = document.getElementById("editor-mode-badge");
  if (badge) {
    badge.textContent = window.USE_DEMO_EDITOR ? "DEMO" : "REALE";
    badge.className = "badge " + (window.USE_DEMO_EDITOR ? "badge-gray" : "badge-green");
  }
});
