// Legge l'URL del backend da ENV (Render -> Environment Variables)
// usa env se c'è, altrimenti forza l'URL del backend (test)
const API_BASE_URL = (import.meta?.env?.VITE_API_BASE_URL || 'https://eccomibook-backend.onrender.com').trim();

// UI helpers
const $ = (s) => document.querySelector(s);
const show = (el) => el.classList.remove("hidden");
const hide = (el) => el.classList.add("hidden");

// Footer anno
$("#year").textContent = new Date().getFullYear();

// Health check backend
async function checkHealth() {
  const dot = $("#health-dot");
  const text = $("#health-text");
  try {
    const r = await fetch(`${API_BASE}/health`, { cache: "no-store" });
    if (!r.ok) throw new Error("not ok");
    const data = await r.json();
    if (data && data.ok) {
      dot.classList.remove("dot-off");
      dot.classList.add("dot-ok");
      text.textContent = "Backend: connesso";
      return;
    }
    throw new Error("invalid");
  } catch {
    dot.classList.remove("dot-ok");
    dot.classList.add("dot-off");
    text.textContent = "Backend: non raggiungibile";
  }
}
checkHealth();

// Navigazione molto semplice: mostra Libreria o Dashboard
function goLibrary() {
  hide($("#dashboard"));
  show($("#library"));
  window.scrollTo({ top: 0, behavior: "smooth" });
}
function goDashboard() {
  hide($("#library"));
  show($("#dashboard"));
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// Bind pulsanti
$("#btn-create").addEventListener("click", () => alert("Azione: Crea Libro (hook da collegare)"));
$("#btn-library").addEventListener("click", goLibrary);
$("#btn-edit").addEventListener("click", () => alert("Azione: Modifica Capitolo (hook da collegare)"));

$("#card-create").addEventListener("click", () => alert("Azione: Crea Libro"));
$("#card-library").addEventListener("click", goLibrary);
$("#card-edit").addEventListener("click", () => alert("Azione: Modifica Capitolo"));

$("#lib-new").addEventListener("click", () => alert("Azione: Nuovo libro"));
$("#empty-create").addEventListener("click", goDashboard);

// (Opzionale) refresh periodico health
setInterval(checkHealth, 15000);
