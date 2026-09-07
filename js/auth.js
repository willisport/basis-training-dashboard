/* Basis · Login & Entschlüsselung für die gehostete (GitHub-Pages-)Version.
   Lokal ohne data/auth-config.json bleibt alles wie bisher, ohne Login. */

const AUTH_SESSION_KEY = "basisAuthSession_v1";

let CURRENT_ROLE = "owner";
let IS_HOSTED = false;

function b64ToBytes(b64) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return bytes;
}
function bytesToB64(bytes) {
  let bin = "";
  bytes.forEach(b => { bin += String.fromCharCode(b); });
  return btoa(bin);
}

async function deriveAesKey(password, saltB64, iterations) {
  const enc = new TextEncoder();
  const salt = b64ToBytes(saltB64);
  const keyMaterial = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations, hash: "SHA-256" },
    keyMaterial, { name: "AES-GCM", length: 256 }, false, ["decrypt"]
  );
}

async function tryUnwrapDek(password, entry, iterations) {
  try {
    const key = await deriveAesKey(password, entry.salt, iterations);
    const iv = b64ToBytes(entry.iv);
    const wrapped = b64ToBytes(entry.wrappedKey);
    const dekBuf = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, wrapped);
    return new Uint8Array(dekBuf);
  } catch {
    return null;
  }
}

async function decryptDataFile(dekRawBytes, encFile) {
  const dekKey = await crypto.subtle.importKey("raw", dekRawBytes, "AES-GCM", false, ["decrypt"]);
  const iv = b64ToBytes(encFile.iv);
  const ct = b64ToBytes(encFile.ciphertext);
  const plainBuf = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, dekKey, ct);
  return JSON.parse(new TextDecoder().decode(plainBuf));
}

function saveSession(dekRawBytes, role) {
  try {
    localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify({ dek: bytesToB64(dekRawBytes), role }));
  } catch { /* ignore */ }
}
function loadSession() {
  try { return JSON.parse(localStorage.getItem(AUTH_SESSION_KEY) || "null"); }
  catch { return null; }
}
function clearSession() {
  try { localStorage.removeItem(AUTH_SESSION_KEY); } catch { /* ignore */ }
}

function showLoginOverlay(authConfig, onSuccess) {
  const overlay = document.createElement("div");
  overlay.className = "login-overlay";
  overlay.innerHTML = `
    <div class="login-card">
      <div class="login-brand">B</div>
      <div class="login-title">Basis</div>
      <div class="login-sub">Passwort eingeben, um dein Trainings-Dashboard zu entschlüsseln.</div>
      <input type="password" id="login-pw" class="login-input" placeholder="Passwort" autofocus />
      <button id="login-submit" class="login-submit-btn">Entsperren</button>
      <div class="login-error" id="login-error"></div>
    </div>`;
  document.body.appendChild(overlay);

  const pwInput = overlay.querySelector("#login-pw");
  const btn = overlay.querySelector("#login-submit");
  const errorEl = overlay.querySelector("#login-error");

  const attempt = async () => {
    const password = pwInput.value;
    if (!password) return;
    btn.disabled = true;
    errorEl.textContent = "";
    const iterations = authConfig.kdf.iterations;

    let dek = await tryUnwrapDek(password, authConfig.owner, iterations);
    let role = "owner";
    if (!dek) {
      dek = await tryUnwrapDek(password, authConfig.viewer, iterations);
      role = "viewer";
    }

    if (!dek) {
      errorEl.textContent = "Falsches Passwort.";
      btn.disabled = false;
      pwInput.select();
      return;
    }

    saveSession(dek, role);
    overlay.remove();
    onSuccess(dek, role);
  };

  btn.addEventListener("click", attempt);
  pwInput.addEventListener("keydown", (e) => { if (e.key === "Enter") attempt(); });
}

function setupLogoutControl() {
  const el = document.getElementById("role-chip");
  if (!el) return;
  el.hidden = false;
  el.textContent = CURRENT_ROLE === "owner" ? "Owner · abmelden" : "Viewer · abmelden";
  el.addEventListener("click", () => {
    clearSession();
    location.reload();
  });
}

/**
 * Boot-Einstiegspunkt: prueft, ob eine verschluesselte gehostete Version
 * vorliegt (data/auth-config.json vorhanden). Falls nein: normales lokales
 * Verhalten wie bisher (training-data.json direkt laden, kein Login).
 * Falls ja: Login-Screen bzw. gespeicherte Session, dann training-data.enc.json
 * entschluesseln.
 */
async function bootWithAuth(onData) {
  let authConfig = null;
  try {
    const res = await fetch("data/auth-config.json", { cache: "no-store" });
    if (res.ok) authConfig = await res.json();
  } catch { /* kein Hosted-Modus */ }

  if (!authConfig) {
    IS_HOSTED = false;
    CURRENT_ROLE = "owner";
    fetch("data/training-data.json")
      .then(r => r.json())
      .then(onData)
      .catch(err => {
        document.getElementById("tab-heute").innerHTML =
          `<div class="card accent-amber"><b>Konnte Trainingsdaten nicht laden.</b><br>${err}<br><br>Läuft die Seite über einen lokalen Server (nicht direkt als Datei geöffnet)?</div>`;
      });
    return;
  }

  IS_HOSTED = true;
  document.body.classList.add("is-hosted");

  const loadEncryptedAndRender = async (dekRawBytes, role) => {
    CURRENT_ROLE = role;
    document.body.classList.toggle("is-viewer", role === "viewer");
    try {
      const encFile = await fetch("data/training-data.enc.json", { cache: "no-store" }).then(r => r.json());
      const data = await decryptDataFile(dekRawBytes, encFile);
      onData(data);
      setupLogoutControl();
    } catch (err) {
      document.getElementById("tab-heute").innerHTML =
        `<div class="card accent-amber"><b>Konnte Daten nicht entschlüsseln.</b><br>${err}</div>`;
    }
  };

  const session = loadSession();
  if (session && session.dek) {
    await loadEncryptedAndRender(b64ToBytes(session.dek), session.role);
    return;
  }

  showLoginOverlay(authConfig, loadEncryptedAndRender);
}
