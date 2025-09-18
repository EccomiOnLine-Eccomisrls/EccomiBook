// Legge la base URL dal build-time env (Render -> VITE_API_BASE_URL)
// Fallback al tuo backend pubblico
const API_BASE_URL =
  (import.meta && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
  "https://eccomibook-backend.onrender.com";

// Stato backend + riga di debug
const statusEl = document.getElementById("backend-status");
(async () => {
  try {
    const r = await fetch(`${API_BASE_URL}/health`, { method: "GET" });
    if (r.ok) {
      statusEl.textContent = "Backend: OK";
    } else {
      statusEl.textContent = `Backend: errore ${r.status}`;
    }
  } catch (e) {
    statusEl.textContent = "Backend: non raggiungibile";
  } finally {
    const dbg = document.createElement("div");
    dbg.style.fontSize = "10px";
    dbg.style.opacity = "0.6";
    dbg.textContent = `API: ${API_BASE_URL}`;
    statusEl.appendChild(dbg);
  }
})();

// Event delegation su tutti i bottoni con data-action
document.addEventListener("click", (ev) => {
  const btn = ev.target.closest("[data-action]");
  if (!btn) return;

  const action = btn.getAttribute("data-action");
  switch (action) {
    case "crea-libro":
      // TODO: sostituire con navigazione reale / chiamata a /books (POST)
      alert("🚀 Crea Libro — (placeholder)");
      break;

    case "libreria":
      // TODO: sostituire con navigazione + fetch /books (GET)
      alert("📚 Libreria — (placeholder)");
      break;

    case "modifica-capitolo":
      // TODO: sostituire con navigazione editor
      alert("✍️ Modifica Capitolo — (placeholder)");
      break;

    default:
      break;
  }
});
