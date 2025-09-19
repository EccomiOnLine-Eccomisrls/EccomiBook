/* =========================================================
 * EccomiBook — Frontend vanilla (Vite)
 * main.js — OPEN MODE (nessuna x-api-key)
 * ========================================================= */

/* ─────────────────────────────────────────────────────────
   Config
   ───────────────────────────────────────────────────────── */

// Editor reale (usa il PUT) — metti a false solo se vuoi bloccarlo.
window.USE_DEMO_EDITOR = true; // imposta a false quando il PUT è pronto

// Base URL API: da env Vite/inline oppure fallback al backend pubblico
const API_BASE_URL =
  (typeof import !== "undefined" &&
    import.meta &&
    import.meta.env &&
    import.meta.env.VITE_API_BASE_URL) ||
  window.VITE_API_BASE_URL ||
  "https://eccomibook-backend.onrender.com";

/* ─────────────────────────────────────────────────────────
   Util
   ───────────────────────────────────────────────────────── */

function $(sel) {
  return document.querySelector(sel);
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

/* ─────────────────────────────────────────────────────────
   Header: badge backend + mini debug
   ───────────────────────────────────────────────────────── */

async function pingBackend() {
  const el = document.getElementById("backend-status");
  if (!el) return;

  setText("backend-status", "Backend: verifico…");
  try {
    const r = await fetch(`${API_BASE_URL}/health`, { method: "GET" });
    if (r.ok) {
      setText("backend-status", "Backend: OK");
    } else {
      setText("backend-status", `Backend: errore ${r.status}`);
    }
  } catch {
    setText("backend-status", "Backend: non raggiungibile");
  }

  // URL API (debug)
  const dbg = document.createElement("div");
  dbg.style.fontSize = "11px";
  dbg.style.opacity = "0.7";
  dbg.style.marginTop = "4px";
  dbg.innerHTML =
    `API: <a href="${API_BASE_URL}" target="_blank" rel="noreferrer">${API_BASE_URL}</a>`;
  el.appendChild(dbg);
}

/* ─────────────────────────────────────────────────────────
   Azioni topbar
   ───────────────────────────────────────────────────────── */

// Crea libro chiamando il backend (OPEN MODE: nessuna x-api-key)
async function createBookSimple() {
  const title = prompt("Titolo del libro:", "Manuale EccomiBook");
  if (!title) return;

  try {
    const res = await fetch(`${API_BASE_URL}/books/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" }, // <-- niente x-api-key
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
    alert(`❌ Errore di rete: ${e?.message || e}\nURL: ${API_BASE_URL}/books/create`);
  }
}

function goLibrary() {
  // placeholder: qui collegheremo GET /books
  alert("Apro la Libreria (coming soon).");
}

function goEditor() {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "block";
  const book = $("#bookIdInput");
  const ch = $("#chapterIdInput");
  const tx = $("#chapterText");
  if (book && !book.value) book.value = (localStorage.getItem("last_book_id") || "book_titolo-di-prova");
  if (ch && !ch.value) ch.value = "ch_0001";
  if (tx && !tx.value) tx.value =
    "Scrivi qui il contenuto del capitolo...\n\n(Modalità " +
    (window.USE_DEMO_EDITOR ? "DEMO" : "REALE") +
    ").";
}

/* ─────────────────────────────────────────────────────────
   Editor Capitolo (DEMO / REALE)
   ───────────────────────────────────────────────────────── */

function closeEditor() {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "none";
}

async function saveChapter() {
  const bookId = $("#bookIdInput")?.value?.trim();
  const chId = $("#chapterIdInput")?.value?.trim();
  const text = $("#chapterText")?.value ?? "";

  if (!bookId || !chId) {
    alert("Inserisci ID libro e ID capitolo.");
    return;
  }

  // DEMO: non chiama API
  if (window.USE_DEMO_EDITOR) {
    alert(
      `(DEMO) Capitolo salvato!\n\nBook: ${bookId}\nChapter: ${chId}\n\nTesto:\n${text.slice(
        0, 200
      )}${text.length > 200 ? "..." : ""}`
    );
    return;
  }

  // REALE: PUT senza x-api-key (open mode)
  try {
    const resp = await fetch(
      `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chId)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" }, // <-- niente x-api-key
        body: JSON.stringify({ content: text }),
      }
    );

    if (!resp.ok) {
      let msg = `Errore ${resp.status}`;
      try {
        const j = await resp.json();
        if (j?.detail) msg = j.detail;
      } catch {}
      throw new Error(msg);
    }

    alert("✅ Capitolo aggiornato con successo!");
  } catch (err) {
    alert("❌ Errore: " + (err?.message || String(err)));
  }
}

/* ─────────────────────────────────────────────────────────
   Hook UI
   ───────────────────────────────────────────────────────── */

function wireButtons() {
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", goLibrary);
  $("#btn-editor")?.addEventListener("click", goEditor);

  $("#btn-quick-new")?.addEventListener("click", createBookSimple);
  $("#btn-lib-open")?.addEventListener("click", goLibrary);
  $("#btn-go-editor")?.addEventListener("click", goEditor);

  $("#btn-ed-save")?.addEventListener("click", saveChapter);
  $("#btn-ed-close")?.addEventListener("click", closeEditor);
}

/* ─────────────────────────────────────────────────────────
   Init
   ───────────────────────────────────────────────────────── */

document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();

  const modeBadge = document.getElementById("editor-mode-badge");
  if (modeBadge) {
    modeBadge.textContent = window.USE_DEMO_EDITOR ? "DEMO" : "REALE";
    modeBadge.className = "badge " + (window.USE_DEMO_EDITOR ? "badge-gray" : "badge-green");
  }
});

/* =========================================================
 * Esporta funzioni usate inline (se servisse)
 * ========================================================= */
window.goEditor = goEditor;
window.saveChapter = saveChapter;
window.closeEditor = closeEditor;
window.createBookSimple = createBookSimple;
