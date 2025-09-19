/* =========================================================
 * EccomiBook — Frontend vanilla (Vite)
 * main.js (COMPLETO)
 * ========================================================= */

import "./styles.css";

/* ────────────────────────────────────────────────
   Config
   ──────────────────────────────────────────────── */
const API_BASE_URL =
  (import.meta?.env?.VITE_API_BASE_URL) ||
  window.VITE_API_BASE_URL ||
  "https://eccomibook-backend.onrender.com";

// Editor: per ora restiamo in DEMO (niente PUT reale)
const USE_DEMO_EDITOR = true;

/* ────────────────────────────────────────────────
   Helpers
   ──────────────────────────────────────────────── */
const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

/** Aggancia lo stesso handler a TUTTI gli elementi che (anche se non dovrebbe) condividono lo stesso id */
function onAll(id, event, handler) {
  $$( `#${id}` ).forEach((el) => el.addEventListener(event, handler));
}

function safeJson(res) {
  return res.json().catch(() => ({}));
}

/* ────────────────────────────────────────────────
   Header: ping backend + pillola URL
   ──────────────────────────────────────────────── */
async function pingBackend() {
  const host = $("#backend-status");
  if (!host) return;

  setText("backend-status", "Backend: verifico…");
  try {
    const r = await fetch(`${API_BASE_URL}/health`, { method: "GET" });
    setText("backend-status", r.ok ? "Backend: ✅ OK" : `Backend: errore ${r.status}`);
  } catch {
    setText("backend-status", "Backend: non raggiungibile");
  }

  // mini debug URL
  const dbg = document.createElement("div");
  dbg.className = "debug-url";
  dbg.innerHTML = `API: <a href="${API_BASE_URL}" target="_blank" rel="noreferrer">${API_BASE_URL}</a>`;
  host.appendChild(dbg);
}

/* ────────────────────────────────────────────────
   Libreria
   ──────────────────────────────────────────────── */
async function fetchLibrary() {
  const listHost = $("#library-list");
  const section  = $("#library-section");
  if (!listHost) return;

  // mostra se è nascosta (scelta: libreria sempre visibile se la sto caricando)
  if (section && section.style.display === "none") section.style.display = "block";

  listHost.innerHTML = `<div class="muted">Carico libreria…</div>`;

  try {
    const res = await fetch(`${API_BASE_URL}/books`, { method: "GET" });
    if (!res.ok) {
      const err = await safeJson(res);
      listHost.innerHTML = `<div class="error">Errore: ${res.status} ${err?.detail || ""}</div>`;
      return;
    }
    const data = await res.json(); // dict: {book_id: {...}, ...}
    renderLibrary(data);
  } catch (e) {
    alert("Errore di rete: " + (e?.message || "Load failed"));
    $("#library-list").innerHTML = `<div class="error">Errore di rete.</div>`;
  }
}

function renderLibrary(booksDict) {
  const listHost = $("#library-list");
  if (!listHost) return;

  const entries = Object.entries(booksDict || {});
  if (entries.length === 0) {
    listHost.innerHTML = `<div class="muted">Nessun libro ancora. Crea il tuo primo libro con “Crea libro”.</div>`;
    return;
  }

  const ul = document.createElement("ul");
  ul.style.listStyle = "none";
  ul.style.padding = "0";
  ul.style.margin  = "0";

  entries
    .sort((a, b) => a[1]?.title?.localeCompare(b[1]?.title || "") || 0)
    .forEach(([id, b]) => {
      const li = document.createElement("li");
      li.className = "card";
      li.style.margin = "10px 0";

      const title   = b?.title || "(senza titolo)";
      const author  = b?.author || "—";
      const lang    = b?.language || "it";

      li.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;">
          <div>
            <div style="font-weight:600">${escapeHtml(title)}</div>
            <div class="muted">Autore: ${escapeHtml(author)} — Lingua: ${escapeHtml(lang)}</div>
            <div class="badge" style="margin-top:6px">${escapeHtml(id)}</div>
          </div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn btn-secondary js-open"  data-id="${id}">Apri</button>
            <button class="btn btn-ghost js-edit"      data-id="${id}">Modifica</button>
            <button class="btn btn-ghost js-delete"    data-id="${id}">Elimina</button>
          </div>
        </div>
      `;
      ul.appendChild(li);
    });

  listHost.innerHTML = "";
  listHost.appendChild(ul);

  // wire pulsanti per card
  $$(".js-open").forEach((btn) =>
    btn.addEventListener("click", () => openEditorFor(btn.dataset.id))
  );
  $$(".js-delete").forEach((btn) =>
    btn.addEventListener("click", () => deleteBook(btn.dataset.id))
  );
  $$(".js-edit").forEach((btn) =>
    btn.addEventListener("click", () => alert("✏️ Modifica libro — in arrivo"))
  );
}

async function deleteBook(bookId) {
  if (!confirm("Eliminare questo libro?")) return;
  try {
    const res = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      const err = await safeJson(res);
      alert(`Errore eliminazione (${res.status}): ${err?.detail || "unknown"}`);
      return;
    }
    await fetchLibrary(); // refresh
  } catch (e) {
    alert("Errore di rete: " + (e?.message || "Delete failed"));
  }
}

/* ────────────────────────────────────────────────
   Creazione libro
   ──────────────────────────────────────────────── */
async function createBookSimple() {
  const title = prompt("Titolo del libro:", "Manuale EccomiBook");
  if (!title) return;

  try {
    const res = await fetch(`${API_BASE_URL}/books/create`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        author: "EccomiBook",
        language: "it",
        chapters: [],
      }),
    });

    if (!res.ok) {
      const err = await safeJson(res);
      alert(`Errore (${res.status}): ${err?.detail || JSON.stringify(err)}`);
      return;
    }

    const data = await res.json();
    try { localStorage.setItem("last_book_id", data.id || data.book_id || ""); } catch {}
    await fetchLibrary(); // aggiorna lista
  } catch (e) {
    alert("Errore di rete: " + (e?.message || "Load failed"));
  }
}

/* ────────────────────────────────────────────────
   Editor capitolo (DEMO)
   ──────────────────────────────────────────────── */
function openEditorFor(bookId) {
  const card = $("#editor-card");
  if (card) card.style.display = "block";

  // pre-compila
  const bookInput = $("#bookIdInput");
  const chInput   = $("#chapterIdInput");
  const area      = $("#chapterText");

  if (bookInput) bookInput.value = bookId || "";
  if (chInput && !chInput.value) chInput.value = "ch_0001";
  if (area) {
    area.value =
      "Scrivi qui il contenuto del capitolo…\n\n" +
      `(Modalità ${USE_DEMO_EDITOR ? "DEMO" : "REALE"})`;
  }

  // badge modalità
  const modeBadge = $("#editor-mode-badge");
  if (modeBadge) {
    modeBadge.textContent = USE_DEMO_EDITOR ? "DEMO" : "REALE";
    modeBadge.className = "badge " + (USE_DEMO_EDITOR ? "badge-gray" : "badge-green");
  }

  // scroll al pannello
  card?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function closeEditor() {
  const card = $("#editor-card");
  if (card) card.style.display = "none";
}

async function saveChapter() {
  const bookId = $("#bookIdInput")?.value?.trim();
  const chId   = $("#chapterIdInput")?.value?.trim();
  const text   = $("#chapterText")?.value ?? "";

  if (!bookId || !chId) {
    alert("Inserisci ID libro e ID capitolo.");
    return;
  }

  if (USE_DEMO_EDITOR) {
    alert(
      `DEMO — salvataggio locale\n\nBook: ${bookId}\nChapter: ${chId}\n\n` +
      text.slice(0, 200) + (text.length > 200 ? "…" : "")
    );
    return;
  }

  // TODO: collegare al tuo endpoint reale quando disponibile:
  // PUT ${API_BASE_URL}/books/{bookId}/chapters/{chId}
  alert("Endpoint reale non ancora collegato.");
}

/* ────────────────────────────────────────────────
   Azioni UI
   ──────────────────────────────────────────────── */
function wireButtons() {
  // Topbar + “Azioni rapide” (id duplicati: li aggancio tutti)
  onAll("btn-create-book", "click", createBookSimple);
  onAll("btn-library",     "click", fetchLibrary);
  onAll("btn-editor",      "click", () => openEditorFor($("#lastBookIdHidden")?.value || ""));

  // Editor card
  $("#btn-ed-save") ?.addEventListener("click", saveChapter);
  $("#btn-ed-close")?.addEventListener("click", closeEditor);
}

/* ────────────────────────────────────────────────
   Utils
   ──────────────────────────────────────────────── */
function escapeHtml(s = "") {
  return s.replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

/* ────────────────────────────────────────────────
   Init
   ──────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();

  // carica libreria al primo avvio
  await fetchLibrary();

  // badge editor (se presente in DOM)
  const modeBadge = $("#editor-mode-badge");
  if (modeBadge) {
    modeBadge.textContent = USE_DEMO_EDITOR ? "DEMO" : "REALE";
    modeBadge.className = "badge " + (USE_DEMO_EDITOR ? "badge-gray" : "badge-green");
  }
});

/* ────────────────────────────────────────────────
   Export (se usi onclick inline in index.html)
   ──────────────────────────────────────────────── */
window.createBookSimple = createBookSimple;
window.fetchLibrary     = fetchLibrary;
window.openEditorFor    = openEditorFor;
window.closeEditor      = closeEditor;
window.saveChapter      = saveChapter;
