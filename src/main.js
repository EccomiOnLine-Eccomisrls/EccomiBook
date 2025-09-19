/* =========================================================
 * EccomiBook — Frontend vanilla (Vite)
 * main.js (completo)
 * ========================================================= */

/* ─────────────────────────────────────────────────────────
   Config
   ───────────────────────────────────────────────────────── */

// Modalità editor: DEMO (true) finché non abilitiamo il PUT reale
window.USE_DEMO_EDITOR = true;

// API base da env (Render → VITE_API_BASE_URL) o fallback pubblico
const API_BASE_URL =
  (import.meta?.env?.VITE_API_BASE_URL) ||
  window.VITE_API_BASE_URL ||
  "https://eccomibook-backend.onrender.com";

/* ─────────────────────────────────────────────────────────
   Utils
   ───────────────────────────────────────────────────────── */
const $ = (sel) => document.querySelector(sel);

function getApiKey() {
  try { return localStorage.getItem("eccomibook_api_key") || ""; } catch { return ""; }
}
function setApiKey(k) {
  try { localStorage.setItem("eccomibook_api_key", k || ""); } catch {}
}
function setText(id, text) { const el = document.getElementById(id); if (el) el.textContent = text; }

/* ─────────────────────────────────────────────────────────
   Header: ping backend + tasto API key
   ───────────────────────────────────────────────────────── */
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

  // URL visibile per debug
  const a = document.createElement("a");
  a.href = API_BASE_URL; a.target = "_blank"; a.rel = "noreferrer";
  a.textContent = API_BASE_URL;
  const wrap = document.createElement("div");
  wrap.style.fontSize = "12px"; wrap.style.opacity = ".8"; wrap.style.marginTop = "4px";
  wrap.append("API: "); wrap.appendChild(a);
  el.appendChild(wrap);

  // Pulsante API key (memorizza in localStorage)
  $("#btn-api-key")?.addEventListener("click", () => {
    const cur = getApiKey();
    const val = prompt("Imposta la tua x-api-key:", cur || "demo_key_owner");
    if (val != null) {
      setApiKey(val.trim());
      alert("API key salvata.");
    }
  });
}

/* ─────────────────────────────────────────────────────────
   Azioni principali (toolbar)
   ───────────────────────────────────────────────────────── */

// 1) Crea libro (chiama il backend)
async function createBookSimple() {
  const title = prompt("Titolo del libro:", "Manuale EccomiBook");
  if (!title) return;

  try {
    const res = await fetch(`${API_BASE_URL}/books/create`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": getApiKey() || "demo_key_owner",
      },
      body: JSON.stringify({
        title,
        author: "EccomiBook",
        language: "it",
        chapters: [],
      }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`Errore (${res.status}): ${err.detail || JSON.stringify(err)}`);
      return;
    }

    const data = await res.json();
    alert(`✅ Libro creato!\nID: ${data.book_id}\nTitolo: ${data.title}`);
    try { localStorage.setItem("last_book_id", data.book_id); } catch {}
  } catch (e) {
    alert("Errore di rete: " + e.message);
  }
}

// 2) Apri Libreria (placeholder)
function goLibrary() {
  alert("Libreria in arrivo: mostreremo l’elenco dei libri creati.");
}

// 3) Mostra Editor capitolo (pannello)
function goEditor() {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "block";
  const book = $("#bookIdInput");
  const ch = $("#chapterIdInput");
  const tx = $("#chapterText");
  if (book && !book.value) book.value = localStorage.getItem("last_book_id") || "book_titolo-di-prova";
  if (ch && !ch.value) ch.value = "ch_0001";
  if (tx && !tx.value) tx.value =
    "Scrivi qui il contenuto del capitolo...\n\n(Modalità " +
    (window.USE_DEMO_EDITOR ? "DEMO" : "REALE") + ").";
}

/* ─────────────────────────────────────────────────────────
   Editor Capitolo (DEMO / REALE)
   ───────────────────────────────────────────────────────── */
function closeEditor() { const ed = $("#editor-card"); if (ed) ed.style.display = "none"; }

async function saveChapter() {
  const bookId = $("#bookIdInput")?.value?.trim();
  const chId = $("#chapterIdInput")?.value?.trim();
  const text = $("#chapterText")?.value ?? "";
  if (!bookId || !chId) { alert("Inserisci ID libro e ID capitolo."); return; }

  if (window.USE_DEMO_EDITOR) {
    alert(`(DEMO) Capitolo salvato!\n\nBook: ${bookId}\nChapter: ${chId}\n\n${text.slice(0,200)}${text.length>200?"...":""}`);
    return;
  }

  try {
    const resp = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chId)}`, {
      method: "PUT",
      headers: { "Content-Type":"application/json", "x-api-key": getApiKey() || "demo_key_owner" },
      body: JSON.stringify({ content: text }),
    });
    if (!resp.ok) {
      let msg = `Errore ${resp.status}`;
      try { const j = await resp.json(); if (j?.detail) msg = j.detail; } catch {}
      throw new Error(msg);
    }
    alert("✅ Capitolo aggiornato con successo!");
  } catch (err) {
    alert("❌ Errore: " + (err?.message || String(err)));
  }
}

/* ─────────────────────────────────────────────────────────
   Wiring + Init
   ───────────────────────────────────────────────────────── */
function wireToolbar() {
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", goLibrary);
  $("#btn-editor")?.addEventListener("click", goEditor);
  $("#btn-ed-save")?.addEventListener("click", saveChapter);
  $("#btn-ed-close")?.addEventListener("click", closeEditor);
}

document.addEventListener("DOMContentLoaded", async () => {
  wireToolbar();
  await pingBackend();

  // Pillola modalità editor
  const badge = document.getElementById("editor-mode-badge");
  if (badge) {
    badge.textContent = window.USE_DEMO_EDITOR ? "DEMO" : "REALE";
    badge.className = "badge";
  }
});

/* Esporta (se servisse inline) */
window.createBookSimple = createBookSimple;
window.goEditor = goEditor;
window.saveChapter = saveChapter;
window.closeEditor = closeEditor;
