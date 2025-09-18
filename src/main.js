const API = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// UI minimale per verificare che tutto funzioni
const app = document.getElementById("app");
app.innerHTML = `
  <header class="topbar">
    <div class="brand">📚 EccomiBook</div>
  </header>

  <main class="container">
    <h1>Benvenuto/a</h1>
    <p>Frontend Vite collegato al backend FastAPI.</p>

    <div class="card">
      <h3>Ping backend</h3>
      <button id="btnHealth">Chiama /health</button>
      <pre id="out"></pre>
    </div>
  </main>
  <footer class="footer">© ${new Date().getFullYear()} EccomiBook</footer>
`;

document.getElementById("btnHealth").onclick = async () => {
  const out = document.getElementById("out");
  out.textContent = "Loading...";
  try {
    const r = await fetch(`${API}/health`);
    out.textContent = await r.text();
  } catch (e) {
    out.textContent = String(e);
  }
};
