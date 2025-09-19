// src/main.js

// =============================
// CONFIG
// =============================
const API_BASE = "https://eccomibook-backend.onrender.com";
const API_KEY = "demo_key_user"; // chiave API demo, poi sostituibile

// =============================
// UTILS
// =============================
function qs(sel) {
  return document.querySelector(sel);
}
function ce(tag, cls) {
  const el = document.createElement(tag);
  if (cls) el.className = cls;
  return el;
}

// =============================
// BACKEND STATUS
// =============================
async function checkBackend() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error("Errore backend");
    qs("#backend-status").innerHTML = `Backend: ✅ OK <br><small>API: ${API_BASE}</small>`;
    qs("#backend-status").style.background = "rgba(0,200,0,0.2)";
  } catch (e) {
    qs("#backend-status").textContent = "Backend: ❌ OFFLINE";
    qs("#backend-status").style.background = "rgba(200,0,0,0.2)";
  }
}

// =============================
// CREA LIBRO
// =============================
async function createBook(title, author, language) {
  const res = await fetch(`${API_BASE}/books/create`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": API_KEY,
    },
    body: JSON.stringify({ title, author, language }),
  });
  if (!res.ok) throw new Error(`Errore HTTP ${res.status}`);
  return await res.json();
}

async function handleCreateBook() {
  const title = prompt("Titolo del libro:", "Nuovo libro") || "EccomiBook";
  const author = "EccomiBook";
  const language = "it";

  try {
    await createBook(title, author, language);
    await loadLibrary();
  } catch (err) {
    alert("Errore creazione libro: " + err.message);
  }
}

// =============================
// LIBRERIA
// =============================
async function fetchBooks() {
  const res = await fetch(`${API_BASE}/books`, {
    headers: { "x-api-key": API_KEY },
  });
  if (!res.ok) throw new Error(`Errore HTTP ${res.status}`);
  return await res.json();
}

async function loadLibrary() {
  const list = qs("#library-list");
  list.innerHTML = "Caricamento...";

  try {
    const books = await fetchBooks();
    list.innerHTML = "";

    if (!books || Object.keys(books).length === 0) {
      list.textContent = "Nessun libro ancora. Crea il tuo primo libro con “Crea libro”.";
      return;
    }

    Object.values(books).forEach((b) => {
      const card = ce("div", "card");
      card.innerHTML = `
        <strong>${b.title || "(senza titolo)"}</strong><br>
        Autore: ${b.author || "—"} — Lingua: ${b.language || "?"}<br>
        <small>${b.id}</small><br>
      `;

      const row = ce("div", "row-right");
      const btnApri = ce("button", "btn btn-ghost");
      btnApri.textContent = "Apri";
      btnApri.onclick = () => openEditor(b.id);

      const btnEdit = ce("button", "btn btn-secondary");
      btnEdit.textContent = "Modifica";
      btnEdit.onclick = () => alert("Funzione modifica WIP");

      const btnDel = ce("button", "btn btn-danger");
      btnDel.textContent = "Elimina";
      btnDel.onclick = () => alert("Funzione elimina WIP");

      row.appendChild(btnApri);
      row.appendChild(btnEdit);
      row.appendChild(btnDel);
      card.appendChild(row);

      list.appendChild(card);
    });
  } catch (err) {
    list.innerHTML = `<span style="color:red;">Errore: ${err.message}</span>`;
  }
}

// =============================
// EDITOR
// =============================
function openEditor(bookId) {
  const editor = qs("#editor-section");
  editor.style.display = "block";
  qs("#editor-book-id").value = bookId;
  qs("#editor-chapter-id").value = "ch_0001";
}
function closeEditor() {
  qs("#editor-section").style.display = "none";
}

// =============================
// NAVIGAZIONE
// =============================
function goLibrary() {
  const lib = qs("#library-section");
  lib.style.display = lib.style.display === "none" ? "block" : "none";
  if (lib.style.display === "block") loadLibrary();
}
function goEditor() {
  openEditor("");
}

// =============================
// EVENT LISTENERS
// =============================
document.addEventListener("DOMContentLoaded", () => {
  checkBackend();

  // Topbar
  qs("#btn-create-book").addEventListener("click", handleCreateBook);
  qs("#btn-library").addEventListener("click", goLibrary);
  qs("#btn-editor").addEventListener("click", goEditor);

  // Azioni rapide
  const quickCreate = document.querySelector(".card .btn.btn-primary");
  if (quickCreate) quickCreate.addEventListener("click", handleCreateBook);

  const quickLibrary = document.querySelector(".card .btn.btn-secondary");
  if (quickLibrary) quickLibrary.addEventListener("click", goLibrary);

  const quickEditor = document.querySelector(".card .btn.btn-ghost");
  if (quickEditor) quickEditor.addEventListener("click", goEditor);

  // Editor
  qs("#btn-close-editor").addEventListener("click", closeEditor);
});
