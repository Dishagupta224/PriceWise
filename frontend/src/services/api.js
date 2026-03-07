import axios from "axios";

const configuredApiBaseUrl = import.meta.env.VITE_API_BASE_URL;
const apiBaseUrl = configuredApiBaseUrl ? configuredApiBaseUrl.replace(/\/+$/, "") : "/api/v1";

const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 10000,
});

const RUNTIME_USER_ID_KEY = "pricewise_runtime_user_id";

function getOrCreateRuntimeUserId() {
  const existing = window.localStorage.getItem(RUNTIME_USER_ID_KEY);
  if (existing) {
    return existing;
  }
  const generated = (window.crypto?.randomUUID?.() || `pw-${Date.now()}-${Math.round(Math.random() * 1e9)}`).slice(0, 64);
  window.localStorage.setItem(RUNTIME_USER_ID_KEY, generated);
  return generated;
}

export async function getProducts(page = 1, filters = {}) {
  const { data } = await api.get("/products", {
    params: {
      page,
      page_size: filters.pageSize ?? 20,
      sort_by: filters.sortBy,
      sort_order: filters.sortOrder,
      category: filters.category || undefined,
      stock_status: filters.stockStatus || undefined,
    },
  });
  return data;
}

export async function getProduct(id) {
  const { data } = await api.get(`/products/${id}`);
  return data;
}

export async function getProductPriceHistory(id, days = 7) {
  const { data } = await api.get(`/products/${id}/price-history`, {
    params: { days },
  });
  return data;
}

export async function getDecisions(page = 1, filters = {}) {
  const { data } = await api.get("/decisions", {
    params: {
      page,
      page_size: filters.pageSize ?? 20,
      decision_type: filters.decisionType || undefined,
      product_id: filters.productId || undefined,
      date_from: filters.dateFrom || undefined,
      date_to: filters.dateTo || undefined,
    },
  });
  return data;
}

export async function getDecision(id) {
  const { data } = await api.get(`/decisions/${id}`);
  return data;
}

export async function getAnalyticsSummary() {
  const { data } = await api.get("/analytics/summary");
  return data;
}

export async function getTopMovers() {
  const { data } = await api.get("/analytics/top-movers");
  return data;
}

export async function createProduct(payload) {
  const { data } = await api.post("/products", payload);
  return data;
}

export async function updateProduct(id, payload) {
  const { data } = await api.put(`/products/${id}`, payload);
  return data;
}

export async function deleteProduct(id) {
  await api.delete(`/products/${id}`);
}

export async function startRuntimeSession() {
  const { data } = await api.post(
    "/runtime-session/start",
    {},
    {
      headers: { "x-user-id": getOrCreateRuntimeUserId() },
    },
  );
  return data;
}

export async function getRuntimeSessionStatus() {
  const { data } = await api.get("/runtime-session/status", {
    headers: { "x-user-id": getOrCreateRuntimeUserId() },
  });
  return data;
}

export default api;
