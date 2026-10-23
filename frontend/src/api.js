const configuredApiBase = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL;
const defaultApiBase = import.meta.env.PROD
  ? "https://talentos-54k8.onrender.com/api/v1"
  : "http://localhost:8000/api/v1";
function normalizeApiBase(value) {
  const base = String(value || "").trim().replace(/\/+$/, "");
  if (!base) return "";
  // Accept either the Render origin or a full /api/v1 base URL, and avoid
  // producing duplicate prefixes when Vercel variables differ by environment.
  if (/\/api\/v1$/i.test(base)) return base;
  return base + "/api/v1";
}
const API_BASE = normalizeApiBase(configuredApiBase || defaultApiBase);

function readableError(detail, fallback) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => {
      if (typeof item === "string") return item;
      const location = Array.isArray(item?.loc) ? item.loc.filter((part) => part !== "body").join(" → ") : "";
      const message = item?.msg || item?.message || "Invalid value";
      return location ? `${location}: ${message}` : message;
    }).join("; ") || fallback;
  }
  if (detail && typeof detail === "object") {
    return detail.message || detail.msg || fallback;
  }
  return fallback;
}

export async function apiRequest(path, options = {}) {
  const token = localStorage.getItem("talentos_access_token");
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const fallback = `Request failed (${response.status})`;
    throw new Error(readableError(payload.detail ?? payload.message, fallback));
  }
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
