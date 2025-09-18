// ---- Config base
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://eccomibook-backend.onrender.com';
const X_API_KEY_STORAGE_KEY = 'eccomibook.x_api_key';

// ---- Utilità
const $ = (sel) => document.querySelector(sel);
const on = (el, ev, fn) => el && el.addEventListener(ev, fn);

// ---- Backend ping + chip di stato
async function checkBackend() {
  const chip = $('#backend-status');
  chip.textContent = 'Backend: verifica…';
  // Mostra l’URL effettivo (mini debug)
  const debug = document.createElement('span');
  debug.style.marginLeft = '8px';
  debug.style.opacity = '0.6';
  debug.style.fontSize = '12px';
  debug.textContent = `API: ${API_BASE_URL}`;
  chip.appendChild(debug);

  try {
    const res = await fetch(`${API_BASE_URL}/health`, { method: 'GET' });
    chip.textContent = res.ok ? 'Backend: OK' : `Backend: errore ${res.status}`;
    chip.appendChild(debug);
  } catch (e) {
    chip.textContent = 'Backend: non raggiungibile';
    chip.appendChild(debug);
  }
}

// ---- Gestione API key
function getApiKey() {
  return localStorage.getItem(X_API_KEY_STORAGE_KEY) || '';
}
function setApiKey(k) {
  localStorage.setItem(X_API_KEY_STORAGE_KEY, k || '');
}
function askApiKey() {
  const cur = getApiKey();
  const k = prompt('Inserisci la tua X-API-KEY', cur || '');
  if (k !== null) setApiKey(k.trim());
}

// ---- Modale Editor (demo)
const modal = $('#modal');
const openModal = () => modal.classList.add('is-open');
const closeModal = () => modal.classList.remove('is-open');

// ---- CTA & Pulsanti
on($('#btn-api-key'), 'click', askApiKey);

on($('#cta-create'), 'click', () => $('#btn-new-book')?.click());
on($('#cta-library'), 'click', () => $('#btn-open-library')?.click());
on($('#cta-edit'), 'click', () => $('#btn-open-editor')?.click());

on($('#btn-new-book'), 'click', async () => {
  const title = prompt('Titolo del libro? (es. Manuale EccomiBook)', 'Manuale EccomiBook');
  if (!title) return;

  const payload = { title, author: 'EccomiBook User', language: 'it' };
  try {
    const res = await fetch(`${API_BASE_URL}/books`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': getApiKey() || 'demo_key_owner'
      },
      body: JSON.stringify(payload)
    });
    const j = await res.json();
    if (!res.ok) throw new Error(j?.detail || 'Errore creazione libro');
    alert(`Creato: ${j.id} — titolo: ${j.title}`);
  } catch (err) {
    alert(`Errore: ${err.message}`);
  }
});

on($('#btn-open-library'), 'click', async () => {
  try {
    const res = await fetch(`${API_BASE_URL}/books`, {
      headers: { 'x-api-key': getApiKey() || 'demo_key_owner' }
    });
    const j = await res.json();
    if (!res.ok) throw new Error(j?.detail || 'Errore libreria');
    alert(`Libri trovati: ${j?.items?.length ?? 0}\n\n${(j?.items||[]).map(b => `• ${b.id} — ${b.title}`).join('\n')}`);
  } catch (err) {
    alert(`Errore: ${err.message}`);
  }
});

on($('#btn-open-editor'), 'click', openModal);
on($('#modal-close'), 'click', closeModal);
on($('#modal-cancel'), 'click', closeModal);
on($('#modal-save'), 'click', () => {
  const bookId = $('#f-book-id').value.trim();
  const chId   = $('#f-ch-id').value.trim();
  const text   = $('#f-ch-text').value.trim();
  if (!bookId || !chId || !text) return alert('Compila i campi per la demo.');
  alert(`(DEMO) Salverei:\nLibro: ${bookId}\nCapitolo: ${chId}\nTesto: ${text.slice(0,60)}…`);
  closeModal();
});

on($('#btn-export-demo'), 'click', async () => {
  const bookId = prompt('ID libro da esportare', 'book_manuale-eccomibook');
  if (!bookId) return;
  try {
    const res = await fetch(`${API_BASE_URL}/generate/export/book/${bookId}`, {
      method: 'POST',
      headers: { 'x-api-key': getApiKey() || 'demo_key_owner' }
    });
    const j = await res.json();
    if (!res.ok) throw new Error(j?.detail || 'Errore export');
    window.open(j.download_url, '_blank');
  } catch (err) {
    alert(`Errore: ${err.message}`);
  }
});

// Init
checkBackend();
