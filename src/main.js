/* =========================================================
 * EccomiBook — Frontend vanilla (Vite)
 * main.js (robusto: azioni rapide + libreria resilienti)
 * ========================================================= */

import "./styles.css";

/* ─────────────────────────────────────────────────────────
   Config
   ───────────────────────────────────────────────────────── */

const API_BASE_URL =
  (import.meta?.env?.VITE_API_BASE_URL) ||
  window.VITE_API_BASE_URL ||
  "https://eccomibook-backend.onrender.com";

// Editor ancora in DEMO finché non abilitiamo il PUT reale
window.USE_DEMO_EDITOR = true;

/* ─────────────────────────────────────────────────────────
   Utilità
   ───────────────────────────────────────────────────────── */

const $ = (sel) => document.querySelector(sel);

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

/* ─────────────────────────────────────────────────────────
   Backend status (pillola in alto)
   ───────────────────────────────────────────────────────── */

async function pingBackend() {
  const el = document.getElementById("backend-status");
  if (!el) return;

  setText("backend-status", "Backend: verifico…");
  try {
    const r = await fetch(`${API_BASE_URL}/health`, { method: "GET" });
    setText("backend-status", r.ok ? "Backend: ✅ OK" : `Backend: errore ${r.status}`);
  } catch {
    setText("backend-status", "Backend: non raggiungibile");
  }

  // mini debug: mostra l'URL API
  const dbg = document.createElement("div");
  dbg.className = "debug-url";
  dbg.innerHTML = `API: <a href="${API_BASE_URL}" target="_blank" rel="noreferrer">${API_BASE_URL}</a>`;
  el.appendChild(dbg);
}

/* ─────────────────────────────────────────────────────────
   Stato / toggle Libreria
   ───────────────────────────────────────────────────────── */

let LIB_OPEN = false;

function setLibOpen(v) {
  LIB_OPEN = !!v;
  try { localStorage.setItem("lib_open", LIB_OPEN ? "1" : "0"); } catch {}
}

function reflectLibraryVisibility() {
  const sec = $("#library-section");
  if (!sec) return;
  sec.style.display = LIB_OPEN ? "block" : "none";
}

function showLibrary() {
  setLibOpen(true);
  reflectLibraryVisibility();
  loadLibrary().catch(() => {});
}

function hideLibrary() {
  setLibOpen(false);
  reflectLibraryVisibility();
}

function toggleLibrary() {
  LIB_OPEN ? hideLibrary() : showLibrary();
}

/* ─────────────────────────────────────────────────────────
   Libreria: caricamento e rendering (resiliente)
   ───────────────────────────────────────────────────────── */

function normalizeBooksPayload(data) {
  // Forma A: è già un array
  if (Array.isArray(data)) return data;

  // Forma B: oggetto con { items: [...] }
  if (data && Array.isArray(data.items)) return data.items;

  // Forma C: dizionario { id1: book1, id2: book2, ... }
  if (data && typeof data === "object") {
    return Object.values(data).filter(
      (v) => v && typeof v === "object" && (("id" in v) || ("title" in v) || ("name" in v))
    );
  }

  // Altre forme sconosciute → array vuoto
  return [];
}

async function loadLibrary() {
  const box = $("#library-list");
  if (!box) return;

  box.innerHTML = `<div class="muted">Carico libreria…</div>`;

  try {
    const res = await fetch(`${API_BASE_URL}/books`, { method: "GET" });
    if (!res.ok) throw new Error(`Errore ${res.status}`);

    const raw = await res.json();
    const items = normalizeBooksPayload(raw);

    if (!items.length) {
      box.innerHTML = `<div class="muted">Nessun libro ancora. Crea il tuo primo libro con “Crea libro”.</div>`;
      return;
    }

    box.innerHTML = "";
    items.forEach((n) => {
      const title = n.title ?? n.name ?? "(senza titolo)";
      const author = n.author ?? n.created_by ?? "—";
      const language = n.language ?? n.lang ?? "it";
      const bid = n.id ?? n.book_id ?? n.slug ?? "";

      const card = document.createElement("div");
      card.className = "card";
      card.style.margin = "10px 0";
      card.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;">
          <div>
            <div style="font-weight:600;">${title}</div>
            <div class="muted">Autore: ${author} — Lingua: ${language}</div>
          </div>
          <div class="badge">${bid}</div>
        </div>
        <div class="row-right" style="margin-top:10px;">
          <button class="btn btn-secondary btn-open">Apri</button>
          <button class="btn btn-ghost btn-edit">Modifica</button>
          <button class="btn btn-ghost btn-delete">Elimina</button>
        </div>
      `;

      card.querySelector(".btn-open")?.addEventListener("click", () => {
        openEditorFor(bid);
        hideLibrary();
      });
      card.querySelector(".btn-edit")?.addEventListener("click", () => {
        alert("Modifica libro — funzione in arrivo (titolo, autore, lingua…).");
      });
      card.querySelector(".btn-delete")?.addEventListener("click", () => {
        alert("Elimina libro — endpoint in arrivo.");
      });

      box.appendChild(card);
    });
  } catch (e) {
    box.innerHTML = `<div class="error">Errore di rete: ${e.message}</div>`;
  }
}

/* ─────────────────────────────────────────────────────────
   Creazione libro
   ───────────────────────────────────────────────────────── */

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
        chapters: []
      })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert(`Errore (${res.status}): ${err.detail || JSON.stringify(err)}`);
      return;
    }

    const data = await res.json();
    alert(`✅ Libro creato!\nID: ${data.book_id}\nTitolo: ${data.title}`);
    try { localStorage.setItem("last_book_id", data.book_id); } catch {}

    // Aggiorna libreria e mostrala
    showLibrary();
  } catch (e) {
    alert("Errore di rete: " + e.message);
  }
}

/* ─────────────────────────────────────────────────────────
   Editor Capitolo (DEMO per ora)
   ───────────────────────────────────────────────────────── */

function openEditor() {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "block";
  const mode = $("#editor-mode-badge");
  if (mode) {
    mode.textContent = window.USE_DEMO_EDITOR ? "DEMO" : "REALE";
    mode.className = "badge " + (window.USE_DEMO_EDITOR ? "badge-gray" : "badge-green");
  }
}

function openEditorFor(bookId) {
  openEditor();
  const b = $("#ed-book-id");
  const ch = $("#ed-chapter-id");
  if (b) b.value = bookId || (b.value || "");
  if (ch && !ch.value) ch.value = "ch_0001";
  const tx = $("#ed-text");
  if (tx && !tx.value) {
    tx.value = `Scrivi qui il contenuto del capitolo...\n\n(Modalità ${window.USE_DEMO_EDITOR ? "DEMO" : "REALE"}).`;
  }
}

function closeEditor() {
  const ed = $("#editor-card");
  if (ed) ed.style.display = "none";
}

async function saveChapter() {
  const bookId = $("#ed-book-id")?.value?.trim();
  const chId = $("#ed-chapter-id")?.value?.trim();
  const text = $("#ed-text")?.value ?? "";

  if (!bookId || !chId) {
    alert("Inserisci ID libro e ID capitolo.");
    return;
  }

  if (window.USE_DEMO_EDITOR) {
    alert(
      `(DEMO) Capitolo salvato!\n\nBook: ${bookId}\nChapter: ${chId}\n\nTesto:\n` +
      text.slice(0, 200) + (text.length > 200 ? "..." : "")
    );
    return;
  }

  // Quando abiliteremo il PUT reale:
  // const resp = await fetch(`${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chId)}`, {
  //   method: "PUT",
  //   headers: { "Content-Type": "application/json" },
  //   body: JSON.stringify({ content: text }),
  // });
  // if (!resp.ok) { const e = await resp.json().catch(()=>({})); throw new Error(e?.detail || `Errore ${resp.status}`);}
  // alert("✅ Capitolo aggiornato con successo!");
}

/* ─────────────────────────────────────────────────────────
   Hook UI (supporta sia ID sia CLASSI nelle azioni rapide)
   ───────────────────────────────────────────────────────── */

function wireButtons() {
  // Topbar
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-library")?.addEventListener("click", toggleLibrary);
  $("#btn-editor")?.addEventListener("click", openEditor);

  // Azioni rapide — ID
  $("#btn-quick-new")?.addEventListener("click", createBookSimple);
  $("#btn-lib-open")?.addEventListener("click", toggleLibrary);
  $("#btn-go-editor")?.addEventListener("click", openEditor);

  // Azioni rapide — CLASSI (fallback se non hai messo gli ID)
  document.querySelector(".qa-create")?.addEventListener("click", createBookSimple);
  document.querySelector(".qa-library")?.addEventListener("click", toggleLibrary);
  document.querySelector(".qa-editor")?.addEventListener("click", openEditor);

  // Editor
  $("#btn-ed-save")?.addEventListener("click", saveChapter);
  $("#btn-ed-close")?.addEventListener("click", closeEditor);

  // Pulsante chiudi nella card libreria (se lo aggiungi nel markup)
  $("#btn-lib-close")?.addEventListener("click", hideLibrary);
}

/* ─────────────────────────────────────────────────────────
   Init
   ───────────────────────────────────────────────────────── */

document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();

  // ripristina stato libreria
  try { LIB_OPEN = localStorage.getItem("lib_open") === "1"; } catch {}
  reflectLibraryVisibility();
  if (LIB_OPEN) loadLibrary().catch(() => {});
});

/* =========================================================
 * Esportati (se servono inline)
 * ========================================================= */
window.showLibrary = showLibrary;
window.hideLibrary = hideLibrary;
window.toggleLibrary = toggleLibrary;
window.openEditor = openEditor;
window.openEditorFor = openEditorFor;
window.closeEditor = closeEditor;
window.saveChapter = saveChapter;
