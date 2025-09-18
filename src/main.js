// ===========================
// Config & helpers API
// ===========================
const API_BASE_URL =
  import.meta?.env?.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  (typeof window !== "undefined" && window.__API_BASE_URL) ||
  "https://eccomibook-backend.onrender.com"; // fallback

const LS_KEY = "eccomibook:x_api_key";

function getApiKey() {
  return localStorage.getItem(LS_KEY) || "";
}
function setApiKey(v) {
  localStorage.setItem(LS_KEY, v || "");
}
function headersJSON() {
  const key = getApiKey();
  return {
    "Content-Type": "application/json",
    ...(key ? { "X-API-Key": key } : {}),
  };
}
async function api(path, opts = {}) {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...opts,
    headers: { ...headersJSON(), ...(opts.headers || {}) },
  });
  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${t}`);
  }
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

// ===========================
// UI mini helpers
// ===========================
const $ = (q) => document.querySelector(q);
const show = (el) => el.classList.remove("hidden");
const hide = (el) => el.classList.add("hidden");

function toast(msg, kind = "info") {
  const box = document.createElement("div");
  box.className = `toast ${kind}`;
  box.textContent = msg;
  document.body.appendChild(box);
  setTimeout(() => box.classList.add("in"), 10);
  setTimeout(() => {
    box.classList.remove("in");
    setTimeout(() => box.remove(), 300);
  }, 2500);
}

// ===========================
// Backend check + key modal
// ===========================
async function checkBackend() {
  const s = $("#backend-status");
  try {
    await api("/health");
    s.textContent = "Backend: OK";
    s.classList.remove("warn");
  } catch (e) {
    s.textContent = "Backend: errore";
    s.classList.add("warn");
  }
  // mini debug
  const dbg = document.createElement("div");
  dbg.className = "muted tiny";
  dbg.textContent = `API: ${API_BASE_URL}`;
  s.after(dbg);
}

function openKeyModal() {
  const dlg = $("#apikey-modal");
  $("#apikey-input").value = getApiKey();
  dlg.showModal();
}
function saveKeyFromModal() {
  const val = $("#apikey-input").value.trim();
  setApiKey(val);
  $("#apikey-modal").close();
  toast("API key salvata", "ok");
  checkBackend();
}

// ===========================
// Features
// ===========================

// 1) CREA LIBRO (POST /books)
async function createBook() {
  try {
    const title = prompt("Titolo del libro", "Manuale EccomiBook");
    if (!title) return;
    const payload = {
      title,
      author: "EccomiBook",
      language: "it",
      genre: "Manuale",
      description: "Guida pratica all'app EccomiBook.",
    };
    const data = await api("/books", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    toast(`Creato: ${data.book_id || data.id || "OK"}`, "ok");
    // mostra subito la libreria
    await loadLibrary();
  } catch (e) {
    console.error(e);
    toast(`Errore creazione libro: ${e.message}`, "err");
  }
}

// 2) LIBRERIA (GET /books)
async function loadLibrary() {
  const sec = $("#library-section");
  const list = $("#library-list");
  list.innerHTML = `<div class="muted">Carico…</div>`;
  show(sec);

  try {
    const data = await api("/books");
    // data shape: dipende dal tuo router; usiamo due fallback comuni
    const items = Array.isArray(data) ? data : (data.items || []);
    if (!items.length) {
      list.innerHTML = `<div class="muted">Nessun libro ancora. Crea il primo!</div>`;
      return;
    }
    // render
    list.innerHTML = "";
    for (const b of items) {
      const id = b.book_id || b.id || "(id)";
      const title = b.title || "(senza titolo)";
      const created = b.created_at || b.created || "";
      const row = document.createElement("div");
      row.className = "row item";
      row.innerHTML = `
        <div>
          <div class="item-title">${title}</div>
          <div class="muted tiny">${id}${created ? " • " + created : ""}</div>
        </div>
        <div class="row gap">
          <button class="btn small" data-id="${id}" data-action="open">Apri</button>
          <button class="btn ghost small" data-id="${id}" data-action="export">Export PDF</button>
        </div>
      `;
      list.appendChild(row);
    }
    // attach actions
    list.onclick = async (e) => {
      const btn = e.target.closest("button[data-action]");
      if (!btn) return;
      const id = btn.dataset.id;
      const act = btn.dataset.action;
      if (act === "export") {
        try {
          const res = await api(`/generate/export/book/${encodeURIComponent(id)}`, {
            method: "POST",
          });
          const url = res.download_url || res.url;
          if (url) {
            window.open(url, "_blank");
          } else {
            toast("Export avviato ma nessun URL ricevuto", "warn");
          }
        } catch (err) {
          toast(`Export errore: ${err.message}`, "err");
        }
      } else if (act === "open") {
        toast(`(demo) Apri libro: ${id}`, "info");
      }
    };
  } catch (e) {
    console.error(e);
    list.innerHTML = `<div class="err">Errore libreria: ${e.message}</div>`;
  }
}

// 3) MODIFICA CAPITOLO (placeholder)
// Quando avremo l’endpoint: PUT /books/{book_id}/chapters/{chapter_id}
async function saveChapterDemo() {
  const bookId = $("#edit-book-id").value.trim();
  const chapterId = $("#edit-chapter-id").value.trim() || `ch_${Math.random().toString(36).slice(2, 8)}`;
  const content = $("#edit-content").value.trim() || "Testo di esempio";
  if (!bookId) {
    toast("Inserisci un ID libro", "warn");
    return;
  }
  // Per ora mostriamo cosa invieremo:
  console.log("PUT payload demo:", { bookId, chapterId, content });
  toast(`(demo) Salverei ${chapterId} nel libro ${bookId}`, "ok");
}

// ===========================
// Wire up UI
// ===========================
function wire() {
  $("#btn-api-key").onclick = openKeyModal;
  $("#apikey-save").onclick = (e) => {
    e.preventDefault();
    saveKeyFromModal();
  };

  // Hero buttons
  $("#btn-create-book").onclick = createBook;
  $("#btn-open-library").onclick = loadLibrary;
  $("#btn-open-editor").onclick = () => { hide($("#library-section")); show($("#editor-section")); };

  // Cards duplicates
  $("#btn-quick-new").onclick = createBook;
  $("#btn-library-card").onclick = loadLibrary;
  $("#btn-editor-card").onclick = () => { hide($("#library-section")); show($("#editor-section")); };

  // Editor
  $("#btn-editor-save").onclick = saveChapterDemo;
  $("#btn-editor-close").onclick = () => hide($("#editor-section"));
}

// ===========================
// Boot
// ===========================
window.addEventListener("DOMContentLoaded", async () => {
  wire();
  // key di comodo in dev
  if (!getApiKey()) setApiKey("demo_key_user");
  await checkBackend();
});
