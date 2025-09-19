/* =========================================================
 * EccomiBook — Frontend vanilla (Vite)
 * Modalità REALE (niente DEMO)
 * ========================================================= */

/* ─────────────────────────────────────────────────────────
   Config
   ───────────────────────────────────────────────────────── */

// API base (Render ENV: VITE_API_BASE_URL) → fallback pubblico
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
   Ping backend + tasto API key
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

  // Impostazione API key
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
   Azioni toolbar
   ───────────────────────────────────────────────────────── */

// Crea libro → POST /books/create
async function createBook() {
  const title = prompt("Titolo del libro:", "Manuale EccomiBook");
  if (!title) return;

  const apiKey = getApiKey();
  if (!apiKey) { alert("Imposta prima la tua API key (in alto a sinistra)."); return; }

  try {
    const res = await fetch(`${API_BASE_URL}/books/create`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": apiKey,
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

// Libreria (placeholder per ora)
function openLibrary() {
  alert("Libreria in arrivo: mostreremo l’elenco dei libri creati.");
}

// Editor Capitolo (reale)
function openEditor() {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "block";
  const book = $("#bookIdInput");
  if (book && !book.value) book.value = localStorage.getItem("last_book_id") || "";
}

function closeEditor() {
  const ed = $("#editor-card"); if (ed) ed.style.display = "none";
}

// PUT /books/{bookId}/chapters/{chapterId}
async function saveChapter() {
  const apiKey = getApiKey();
  if (!apiKey) { alert("Imposta prima la tua API key (in alto a sinistra)."); return; }

  const bookId = $("#bookIdInput")?.value?.trim();
  const chId = $("#chapterIdInput")?.value?.trim();
  const text = $("#chapterText")?.value ?? "";

  if (!bookId || !chId) {
    alert("Inserisci ID libro e ID capitolo.");
    return;
  }

  try {
    const resp = await fetch(
      `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chId)}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": apiKey,
        },
        body: JSON.stringify({ content: text }),
      }
    );

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
function wireUI() {
  $("#btn-create-book")?.addEventListener("click", createBook);
  $("#btn-library")?.addEventListener("click", openLibrary);
  $("#btn-editor")?.addEventListener("click", openEditor);
  $("#btn-ed-save")?.addEventListener("click", saveChapter);
  $("#btn-ed-close")?.addEventListener("click", closeEditor);
}

document.addEventListener("DOMContentLoaded", async () => {
  wireUI();
  await pingBackend();
});

// (opzionale) export global, se servisse inline
window.createBook = createBook;
window.openEditor = openEditor;
window.saveChapter = saveChapter;
window.closeEditor = closeEditor;
