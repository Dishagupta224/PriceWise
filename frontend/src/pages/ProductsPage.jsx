import { Pencil, Plus, Trash2, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import EmptyState from "../components/EmptyState";
import LoadingPanel from "../components/LoadingPanel";
import { useLiveFeed } from "../context/LiveFeedContext";
import { createProduct, deleteProduct, getProducts, updateProduct } from "../services/api";
import { formatCurrency, formatPercent, formatNumber, stockTone } from "../utils/formatters";

const PAGE_SIZE = 20;
const BACKEND_SORT_MAP = {
  name: "name",
  ourPrice: "price",
  costPrice: "name",
  stock: "stock",
  category: "name",
  competitor: "name",
  gap: "name",
  margin: "name",
};

const EMPTY_PRODUCT_FORM = {
  id: null,
  name: "",
  category: "",
  description: "",
  our_price: "",
  cost_price: "",
  stock_quantity: "",
  min_margin_percent: "20",
  is_active: true,
};

function getBestCompetitor(product) {
  return product.latest_competitor_prices?.[0] || null;
}

function getPriceGapPercent(product) {
  const competitor = getBestCompetitor(product);
  if (!competitor) {
    return null;
  }

  const bestCompetitorPrice = Number(competitor.price);
  const ourPrice = Number(product.our_price);
  if (!bestCompetitorPrice) {
    return null;
  }

  return ((ourPrice - bestCompetitorPrice) / bestCompetitorPrice) * 100;
}

function sortProducts(products, sortBy, sortOrder) {
  const direction = sortOrder === "asc" ? 1 : -1;

  return [...products].sort((left, right) => {
    const leftCompetitor = getBestCompetitor(left);
    const rightCompetitor = getBestCompetitor(right);
    const leftGap = getPriceGapPercent(left);
    const rightGap = getPriceGapPercent(right);

    const valueMap = {
      name: left.name.localeCompare(right.name),
      category: left.category.localeCompare(right.category),
      ourPrice: Number(left.our_price) - Number(right.our_price),
      costPrice: Number(left.cost_price) - Number(right.cost_price),
      competitor:
        Number(leftCompetitor?.price ?? Number.POSITIVE_INFINITY) -
        Number(rightCompetitor?.price ?? Number.POSITIVE_INFINITY),
      gap: Number(leftGap ?? Number.POSITIVE_INFINITY) - Number(rightGap ?? Number.POSITIVE_INFINITY),
      stock: Number(left.stock_quantity) - Number(right.stock_quantity),
      margin: Number(left.current_margin_percent) - Number(right.current_margin_percent),
    };

    const result = valueMap[sortBy] ?? 0;
    if (result === 0) {
      return left.name.localeCompare(right.name) * direction;
    }
    return result * direction;
  });
}

function SortHeader({ label, sortKey, sortBy, sortOrder, onToggle }) {
  const active = sortBy === sortKey;

  return (
    <th>
      <button
        type="button"
        className="inline-flex items-center gap-2 text-left text-xs uppercase tracking-[0.22em] text-muted transition hover:text-slate-100"
        onClick={() => onToggle(sortKey)}
      >
        <span>{label}</span>
        <span className={active ? "text-slate-100" : "text-muted/60"}>
          {active ? (sortOrder === "asc" ? "ASC" : "DESC") : "SORT"}
        </span>
      </button>
    </th>
  );
}

function ProductsPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const stockStatusParam = searchParams.get("stockStatus");
  const sortByParam = searchParams.get("sortBy");
  const sortOrderParam = searchParams.get("sortOrder");
  const initialStockStatus = ["low", "normal", "out"].includes(stockStatusParam || "") ? stockStatusParam : "";
  const initialSortBy = ["name", "category", "ourPrice", "costPrice", "competitor", "gap", "stock", "margin"].includes(sortByParam || "")
    ? sortByParam
    : "name";
  const initialSortOrder = ["asc", "desc"].includes(sortOrderParam || "") ? sortOrderParam : "asc";
  const { messages } = useLiveFeed();
  const [response, setResponse] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [page, setPage] = useState(1);
  const [feedback, setFeedback] = useState("");
  const [deleteDialog, setDeleteDialog] = useState({ open: false, product: null });
  const [dialog, setDialog] = useState({
    open: false,
    mode: "create",
    form: EMPTY_PRODUCT_FORM,
    error: "",
  });
  const [filters, setFilters] = useState({
    category: "",
    stockStatus: initialStockStatus || "",
    sortBy: initialSortBy,
    sortOrder: initialSortOrder,
  });

  async function loadProductsData(targetPage = page, nextFilters = filters, showLoading = true) {
    try {
      if (showLoading) {
        setIsLoading(true);
      }
      const data = await getProducts(targetPage, {
        ...nextFilters,
        pageSize: PAGE_SIZE,
        sortBy: BACKEND_SORT_MAP[nextFilters.sortBy],
      });
      setResponse(data);
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        await loadProductsData(page, filters, true);
        if (!isMounted) {
          return;
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    load();
    return () => {
      isMounted = false;
    };
  }, [page, filters]);

  useEffect(() => {
    const latestMessage = messages[0];
    if (!latestMessage || !["PRICE_CHANGE", "AGENT_DECISION", "ALERT"].includes(latestMessage.type)) {
      return;
    }

    const timer = window.setTimeout(async () => {
      await loadProductsData(page, filters, false);
    }, 400);

    return () => window.clearTimeout(timer);
  }, [messages, page, filters]);

  const rawProducts = response?.items || [];
  const products = useMemo(
    () => sortProducts(rawProducts, filters.sortBy, filters.sortOrder),
    [rawProducts, filters.sortBy, filters.sortOrder],
  );
  const categories = useMemo(
    () => Array.from(new Set(rawProducts.map((item) => item.category).filter(Boolean))).sort(),
    [rawProducts],
  );
  const pagination = response?.pagination;

  function updateFilter(key, value) {
    setPage(1);
    setFilters((current) => ({ ...current, [key]: value }));
  }

  function toggleSort(sortKey) {
    setFilters((current) => ({
      ...current,
      sortBy: sortKey,
      sortOrder: current.sortBy === sortKey && current.sortOrder === "asc" ? "desc" : "asc",
    }));
  }

  function openCreateDialog() {
    setDialog({
      open: true,
      mode: "create",
      form: EMPTY_PRODUCT_FORM,
      error: "",
    });
  }

  function openEditDialog(product) {
    setDialog({
      open: true,
      mode: "edit",
      form: {
        id: product.id,
        name: product.name ?? "",
        category: product.category ?? "",
        description: product.description ?? "",
        our_price: String(product.our_price ?? ""),
        cost_price: String(product.cost_price ?? ""),
        stock_quantity: String(product.stock_quantity ?? ""),
        min_margin_percent: String(product.min_margin_percent ?? "20"),
        is_active: Boolean(product.is_active),
      },
      error: "",
    });
  }

  function closeDialog() {
    if (isSaving) {
      return;
    }
    setDialog({
      open: false,
      mode: "create",
      form: EMPTY_PRODUCT_FORM,
      error: "",
    });
  }

  function updateDialogField(field, value) {
    setDialog((current) => ({
      ...current,
      error: "",
      form: {
        ...current.form,
        [field]: value,
      },
    }));
  }

  async function submitDialog() {
    const form = dialog.form;
    const payload = {
      name: String(form.name || "").trim(),
      category: String(form.category || "").trim(),
      description: String(form.description || "").trim(),
      our_price: Number(form.our_price),
      cost_price: Number(form.cost_price),
      stock_quantity: Number(form.stock_quantity),
      min_margin_percent: Number(form.min_margin_percent),
      is_active: Boolean(form.is_active),
    };

    if (!payload.name || !payload.category) {
      setDialog((current) => ({ ...current, error: "Name and category are required." }));
      return;
    }
    if (!Number.isFinite(payload.our_price) || payload.our_price <= 0) {
      setDialog((current) => ({ ...current, error: "Our price must be greater than 0." }));
      return;
    }
    if (!Number.isFinite(payload.cost_price) || payload.cost_price <= 0) {
      setDialog((current) => ({ ...current, error: "Cost price must be greater than 0." }));
      return;
    }
    if (!Number.isInteger(payload.stock_quantity) || payload.stock_quantity < 0) {
      setDialog((current) => ({ ...current, error: "Stock quantity must be a non-negative whole number." }));
      return;
    }

    try {
      setIsSaving(true);
      setFeedback("");
      if (dialog.mode === "create") {
        await createProduct(payload);
        setFeedback(`Created product "${payload.name}".`);
      } else {
        await updateProduct(form.id, payload);
        setFeedback(`Updated product "${payload.name}".`);
      }
      closeDialog();
      await loadProductsData(1, filters, false);
      setPage(1);
    } catch (saveError) {
      setDialog((current) => ({
        ...current,
        error: saveError?.response?.data?.detail || saveError.message || "Failed to save product.",
      }));
    } finally {
      setIsSaving(false);
    }
  }

  function openDeleteDialog(product) {
    setDeleteDialog({ open: true, product });
  }

  function closeDeleteDialog() {
    if (isSaving) {
      return;
    }
    setDeleteDialog({ open: false, product: null });
  }

  async function confirmDelete() {
    const product = deleteDialog.product;
    if (!product) {
      return;
    }
    try {
      setIsSaving(true);
      setFeedback("");
      await deleteProduct(product.id);
      setFeedback(`Deleted product "${product.name}".`);
      closeDeleteDialog();
      await loadProductsData(1, filters, false);
      setPage(1);
    } catch (deleteError) {
      setFeedback(deleteError?.response?.data?.detail || deleteError.message || "Failed to delete product.");
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading && !response) {
    return <LoadingPanel label="Loading products..." />;
  }

  return (
    <div className="space-y-6">
      <section className="panel p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <p className="text-sm text-muted">Manage your product catalog: add, edit, or delete products.</p>
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-xl border border-accent/40 bg-accent/10 px-4 py-2 text-sm text-slate-100"
            onClick={openCreateDialog}
          >
            <Plus size={16} />
            Add Product
          </button>
        </div>
        <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
          <label className="space-y-2">
            <span className="label">Category</span>
            <select
              className="input-shell w-full"
              value={filters.category}
              onChange={(event) => updateFilter("category", event.target.value)}
            >
              <option value="">All categories</option>
              {categories.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2">
            <span className="label">Stock Status</span>
            <select
              className="input-shell w-full"
              value={filters.stockStatus}
              onChange={(event) => updateFilter("stockStatus", event.target.value)}
            >
              <option value="">All</option>
              <option value="low">Low</option>
              <option value="out">Out of Stock</option>
              <option value="normal">Normal</option>
            </select>
          </label>
        </div>
        {feedback ? <p className="mt-4 text-sm text-muted">{feedback}</p> : null}
      </section>

      {products.length === 0 ? (
        <EmptyState
          title="No products found"
          description="Adjust the filters or seed the backend catalog to populate this table."
        />
      ) : (
        <section className="space-y-4">
          <div className="table-shell overflow-x-auto">
            <table className="min-w-[1320px]">
              <thead>
                <tr>
                  <SortHeader label="Product Name" sortKey="name" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                  <SortHeader label="Category" sortKey="category" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                  <SortHeader label="Our Price" sortKey="ourPrice" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                  <SortHeader label="Cost Price" sortKey="costPrice" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                  <SortHeader label="Best Competitor Price" sortKey="competitor" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                  <SortHeader label="Price Gap" sortKey="gap" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                  <SortHeader label="Stock" sortKey="stock" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                  <SortHeader label="Margin %" sortKey="margin" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                  <th className="text-xs uppercase tracking-[0.22em] text-muted">Actions</th>
                </tr>
              </thead>
              <tbody>
                {products.map((product) => {
                  const bestCompetitor = getBestCompetitor(product);
                  const gap = getPriceGapPercent(product);

                  return (
                    <tr
                      key={product.id}
                      className="cursor-pointer"
                      onClick={() => navigate(`/products/${product.id}`)}
                    >
                      <td>
                        <div className="flex items-center gap-3">
                          <div className="rounded-xl bg-accent/10 p-2 text-accent">
                            <Search size={14} />
                          </div>
                          <div>
                            <p className="font-medium text-slate-100">{product.name}</p>
                            <p className="text-xs text-muted">#{product.id}</p>
                          </div>
                        </div>
                      </td>
                      <td>{product.category}</td>
                      <td>{formatCurrency(product.our_price)}</td>
                      <td>{formatCurrency(product.cost_price)}</td>
                      <td>{bestCompetitor ? formatCurrency(bestCompetitor.price) : "--"}</td>
                      <td
                        className={
                          gap === null
                            ? "text-muted"
                            : gap <= 0
                              ? "text-success"
                              : gap <= 3
                                ? "text-warning"
                                : "text-danger"
                        }
                      >
                        {gap === null ? "--" : formatPercent(gap)}
                      </td>
                      <td>
                        <span className={`font-semibold ${stockTone(product.stock_quantity)}`}>
                          {formatNumber(product.stock_quantity)}
                        </span>
                      </td>
                      <td>{formatPercent(product.current_margin_percent)}</td>
                      <td>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            className="rounded-lg border border-line/70 p-2 text-slate-100"
                            onClick={(event) => {
                              event.stopPropagation();
                              openEditDialog(product);
                            }}
                            title="Edit product"
                          >
                            <Pencil size={14} />
                          </button>
                          <button
                            type="button"
                            className="rounded-lg border border-danger/40 p-2 text-danger disabled:opacity-50"
                            onClick={(event) => {
                              event.stopPropagation();
                              openDeleteDialog(product);
                            }}
                            disabled={isSaving}
                            title="Delete product"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="panel flex items-center justify-between px-5 py-4">
            <div className="text-sm text-muted">
              Showing page {pagination?.page || page} of {pagination?.total_pages || 1} |{" "}
              {formatNumber(pagination?.total_items || products.length)} products
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="rounded-xl border border-line/70 bg-slate-900/[0.35] p-2 text-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
                onClick={() => setPage((current) => Math.max(current - 1, 1))}
                disabled={(pagination?.page || page) <= 1}
              >
                <ChevronLeft size={16} />
              </button>
              <button
                type="button"
                className="rounded-xl border border-line/70 bg-slate-900/[0.35] p-2 text-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
                onClick={() => setPage((current) => current + 1)}
                disabled={(pagination?.page || page) >= (pagination?.total_pages || 1)}
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        </section>
      )}

      {dialog.open ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/70 px-4">
          <div className="panel w-full max-w-2xl p-5">
            <p className="label">{dialog.mode === "create" ? "Add Product" : "Edit Product"}</p>
            <h3 className="mt-1 text-lg font-semibold text-slate-50">
              {dialog.mode === "create" ? "Create a new catalog item" : `Update ${dialog.form.name || "product"}`}
            </h3>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <label className="space-y-2">
                <span className="label">Name</span>
                <input className="input-shell w-full px-3 py-2" value={dialog.form.name} onChange={(e) => updateDialogField("name", e.target.value)} />
              </label>
              <label className="space-y-2">
                <span className="label">Category</span>
                <input className="input-shell w-full px-3 py-2" value={dialog.form.category} onChange={(e) => updateDialogField("category", e.target.value)} />
              </label>
              <label className="space-y-2">
                <span className="label">Our Price</span>
                <input type="number" min="0" step="0.01" className="input-shell w-full px-3 py-2" value={dialog.form.our_price} onChange={(e) => updateDialogField("our_price", e.target.value)} />
              </label>
              <label className="space-y-2">
                <span className="label">Cost Price</span>
                <input type="number" min="0" step="0.01" className="input-shell w-full px-3 py-2" value={dialog.form.cost_price} onChange={(e) => updateDialogField("cost_price", e.target.value)} />
              </label>
              <label className="space-y-2">
                <span className="label">Stock Quantity</span>
                <input type="number" min="0" step="1" className="input-shell w-full px-3 py-2" value={dialog.form.stock_quantity} onChange={(e) => updateDialogField("stock_quantity", e.target.value)} />
              </label>
              <label className="space-y-2">
                <span className="label">Min Margin %</span>
                <input type="number" min="0" max="100" step="0.01" className="input-shell w-full px-3 py-2" value={dialog.form.min_margin_percent} onChange={(e) => updateDialogField("min_margin_percent", e.target.value)} />
              </label>
              <label className="space-y-2 md:col-span-2">
                <span className="label">Description</span>
                <textarea className="input-shell min-h-24 w-full px-3 py-2" value={dialog.form.description} onChange={(e) => updateDialogField("description", e.target.value)} />
              </label>
              <label className="flex items-center gap-2 md:col-span-2">
                <input type="checkbox" checked={dialog.form.is_active} onChange={(e) => updateDialogField("is_active", e.target.checked)} />
                <span className="text-sm text-slate-100">Active product</span>
              </label>
            </div>
            {dialog.error ? <p className="mt-3 text-sm text-danger">{dialog.error}</p> : null}
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" className="rounded-lg border border-line/70 px-4 py-2 text-sm text-muted" onClick={closeDialog} disabled={isSaving}>
                Cancel
              </button>
              <button type="button" className="rounded-lg border border-accent/40 bg-accent/10 px-4 py-2 text-sm text-slate-100 disabled:opacity-50" onClick={submitDialog} disabled={isSaving}>
                {isSaving ? "Saving..." : dialog.mode === "create" ? "Create Product" : "Save Changes"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {deleteDialog.open ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/70 px-4">
          <div className="panel w-full max-w-md p-5">
            <p className="label">Delete Product</p>
            <h3 className="mt-1 text-lg font-semibold text-slate-50">{deleteDialog.product?.name}</h3>
            <p className="mt-2 text-sm text-muted">This action cannot be undone.</p>
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" className="rounded-lg border border-line/70 px-4 py-2 text-sm text-muted" onClick={closeDeleteDialog} disabled={isSaving}>
                Cancel
              </button>
              <button type="button" className="rounded-lg border border-danger/40 bg-danger/10 px-4 py-2 text-sm text-danger disabled:opacity-50" onClick={confirmDelete} disabled={isSaving}>
                {isSaving ? "Deleting..." : "Delete Product"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default ProductsPage;
