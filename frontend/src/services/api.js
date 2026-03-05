import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  timeout: 10000,
});

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

export default api;
