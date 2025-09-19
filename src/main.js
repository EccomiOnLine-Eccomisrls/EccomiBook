/* =========================================================
 * EccomiBook — Frontend vanilla (Vite)
 * main.js (completo)
 * ========================================================= */

/* ─────────────────────────────────────────────────────────
   Config
   ───────────────────────────────────────────────────────── */

// Imposta true per restare in modalità DEMO (non chiama il backend per il PUT).
// Quando attivi l'endpoint reale /books/{id}/chapters/{id} (PUT), metti false.
window.USE_DEMO_EDITOR = true;

// API base: ENV di Vite/Render oppure fallback al backend pubblico
const API_BASE_URL =
  (import.meta && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
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

function getApiKey() {
  try {
    return localStorage.getItem("eccomibook_api_key") || "";
  } catch {
    return "";
  }
}

function setApiKey(k) {
  try {
    localStorage.setItem("eccomibook_api_key", k || "");
  } catch {}
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

  // Mini debug: mostra l'URL effettivo
  const dbg = document.createElement("div");
  dbg.style.fontSize = "11px";
  dbg.style.opacity = "0.7";
  dbg.style.marginTop = "4px";
  dbg.innerHTML =
    `API: <a href="${API_BASE_URL}" target="_blank" rel="noreferrer">${API_BASE_URL}</a>`;
  el.appendChild(dbg);

  // Pulsante rapido per impostare la x-api-key
  const kbtn = document.createElement("button");
  kbtn.textContent = "API key";
  kbtn.style.marginTop = "6px";
  kbtn.className = "btn btn-xs";
  kbtn.onclick = () => {
    const cur = getApiKey();
    const val = prompt("Imposta la tua x-api-key:", cur || "demo_key_owner");
    if (val != null) {
      setApiKey(val.trim());
      alert("API key salvata.");
    }
  };
  el.appendChild(document.createElement("br"));
  el.appendChild(kbtn);
}

/* ─────────────────────────────────────────────────────────
   Azioni topbar
   ───────────────────────────────────────────────────────── */

// Crea libro chiamando il backend
async function createBookSimple() {
  const title = prompt("Titolo del libro:", "Manuale EccomiBook");
  if (!title) return;

  try {
    const res = await fetch(`${API_BASE_URL}/books/create`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": getApiKey() || "demo_key_user", // in dev puoi usare demo_key_owner
      },
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
  } catch (e) {
    alert("Errore di rete: " + (e?.message || String(e)));
  }
}

function goLibrary() {
  // Prossimo step: colleghiamo GET /books per mostrare l’elenco
  alert("Apro la Libreria (elenco libri)… in arrivo!");
}

function goEditor() {
  // Mostra il pannello editor nella pagina (ancorato in fondo)
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
  const chId   = $("#chapterIdInput")?.value?.trim();
  const text   = $("#chapterText")?.value ?? "";

  if (!bookId || !chId) {
    alert("Inserisci ID libro e ID capitolo.");
    return;
  }

  if (window.USE_DEMO_EDITOR) {
    alert(
      `(DEMO) Capitolo salvato!\n\nBook: ${bookId}\nChapter: ${chId}\n\nTesto:\n${text.slice(
        0, 200
      )}${text.length > 200 ? "..." : ""}`
    );
    return;
  }

  // Modalità reale: chiama PUT backend
  try {
    const resp = await fetch(
      `${API_BASE_URL}/books/${encodeURIComponent(bookId)}/chapters/${encodeURIComponent(chId)}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "x-api-key": getApiKey() || "demo_key_owner",
        },
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
  // Crea libro
  $("#btn-create-book")?.addEventListener("click", createBookSimple);
  $("#btn-quick-new")?.addEventListener("click", createBookSimple);

  // Libreria & Editor
  $("#btn-library")?.addEventListener("click", goLibrary);
  $("#btn-lib-open")?.addEventListener("click", goLibrary);
  $("#btn-editor")?.addEventListener("click", goEditor);
  $("#btn-go-editor")?.addEventListener("click", goEditor);

  // Editor actions
  $("#btn-ed-save")?.addEventListener("click", saveChapter);
  $("#btn-ed-close")?.addEventListener("click", closeEditor);
}

/* ─────────────────────────────────────────────────────────
   Init
   ───────────────────────────────────────────────────────── */

document.addEventListener("DOMContentLoaded", async () => {
  wireButtons();
  await pingBackend();

  // Mostra la “pillola” modalità editor (demo/reale)
  const modeBadge = document.getElementById("editor-mode-badge");
  if (modeBadge) {
    modeBadge.textContent = window.USE_DEMO_EDITOR ? "DEMO" : "REALE";
    modeBadge.className = "badge " + (window.USE_DEMO_EDITOR ? "badge-gray" : "badge-green");
  }
});

/* =========================================================
 * Esporta funzioni usate inline in index.html (se servisse)
 * ========================================================= */
window.goEditor   = goEditor;
window.saveChapter = saveChapter;
window.closeEditor = closeEditor;
window.createBookSimple = createBookSimple; // opzionale
