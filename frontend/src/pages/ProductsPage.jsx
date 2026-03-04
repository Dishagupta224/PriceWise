import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import EmptyState from "../components/EmptyState";
import LoadingPanel from "../components/LoadingPanel";
import { useLiveFeed } from "../context/LiveFeedContext";
import { getProducts } from "../services/api";
import { formatCurrency, formatPercent, formatNumber, stockTone } from "../utils/formatters";

const PAGE_SIZE = 20;
const BACKEND_SORT_MAP = {
  name: "name",
  ourPrice: "price",
  stock: "stock",
  category: "name",
  competitor: "name",
  gap: "name",
  margin: "name",
  status: "name",
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

function getProductStatus(product) {
  const gap = getPriceGapPercent(product);
  if (gap === null || gap <= 0) {
    return { label: "Winning", className: "border-success/30 bg-success/10 text-success" };
  }
  if (gap <= 3) {
    return { label: "At Risk", className: "border-warning/30 bg-warning/10 text-warning" };
  }
  return { label: "Losing", className: "border-danger/30 bg-danger/10 text-danger" };
}

function sortProducts(products, sortBy, sortOrder) {
  const direction = sortOrder === "asc" ? 1 : -1;

  return [...products].sort((left, right) => {
    const leftCompetitor = getBestCompetitor(left);
    const rightCompetitor = getBestCompetitor(right);
    const leftGap = getPriceGapPercent(left);
    const rightGap = getPriceGapPercent(right);
    const leftStatus = getProductStatus(left).label;
    const rightStatus = getProductStatus(right).label;

    const valueMap = {
      name: left.name.localeCompare(right.name),
      category: left.category.localeCompare(right.category),
      ourPrice: Number(left.our_price) - Number(right.our_price),
      competitor:
        Number(leftCompetitor?.price ?? Number.POSITIVE_INFINITY) -
        Number(rightCompetitor?.price ?? Number.POSITIVE_INFINITY),
      gap: Number(leftGap ?? Number.POSITIVE_INFINITY) - Number(rightGap ?? Number.POSITIVE_INFINITY),
      stock: Number(left.stock_quantity) - Number(right.stock_quantity),
      margin: Number(left.current_margin_percent) - Number(right.current_margin_percent),
      status: leftStatus.localeCompare(rightStatus),
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
  const { messages } = useLiveFeed();
  const [response, setResponse] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({
    category: "",
    stockStatus: "",
    sortBy: "name",
    sortOrder: "asc",
  });

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        setIsLoading(true);
        const data = await getProducts(page, {
          ...filters,
          pageSize: PAGE_SIZE,
          sortBy: BACKEND_SORT_MAP[filters.sortBy],
        });
        if (isMounted) {
          setResponse(data);
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
      const refreshed = await getProducts(page, {
        ...filters,
        pageSize: PAGE_SIZE,
        sortBy: BACKEND_SORT_MAP[filters.sortBy],
      });
      setResponse(refreshed);
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

  if (isLoading && !response) {
    return <LoadingPanel label="Loading products..." />;
  }

  return (
    <div className="space-y-6">
      <section className="panel p-5">
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
      </section>

      {products.length === 0 ? (
        <EmptyState
          title="No products found"
          description="Adjust the filters or seed the backend catalog to populate this table."
        />
      ) : (
        <section className="space-y-4">
          <div className="table-shell">
            <table>
              <thead>
                <tr>
                  <SortHeader label="Product Name" sortKey="name" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                  <SortHeader label="Category" sortKey="category" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                  <SortHeader label="Our Price" sortKey="ourPrice" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                  <SortHeader label="Best Competitor Price" sortKey="competitor" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                  <SortHeader label="Price Gap" sortKey="gap" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                  <SortHeader label="Stock" sortKey="stock" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                  <SortHeader label="Margin %" sortKey="margin" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                  <SortHeader label="Status" sortKey="status" sortBy={filters.sortBy} sortOrder={filters.sortOrder} onToggle={toggleSort} />
                </tr>
              </thead>
              <tbody>
                {products.map((product) => {
                  const bestCompetitor = getBestCompetitor(product);
                  const gap = getPriceGapPercent(product);
                  const status = getProductStatus(product);

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
                        <span className={`status-pill ${status.className}`}>{status.label}</span>
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
    </div>
  );
}

export default ProductsPage;
