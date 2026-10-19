const configuredApiBase = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL;
const defaultApiBase = import.meta.env.PROD
  ? "https://talentos-54k8.onrender.com/api/v1"
  : "http://localhost:8000/api/v1";
const API_BASE = (configuredApiBase || defaultApiBase).replace(/\/$/, "");

export async function apiRequest(path, options = {}) {
  const token = localStorage.getItem("talentos_access_token");
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || payload.message || `Request failed (${response.status})`);
  return payload;
}

export function saveSession(data) {
  localStorage.setItem("talentos_access_token", data.access_token);
  localStorage.setItem("talentos_user", JSON.stringify(data.user));
}

export function clearSession() {
  localStorage.removeItem("talentos_access_token");
  localStorage.removeItem("talentos_user");
}
