import { AlertTriangle, PackageX } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import EmptyState from "../components/EmptyState";
import LoadingPanel from "../components/LoadingPanel";
import { useLiveFeed } from "../context/LiveFeedContext";
import { getProducts, updateProduct } from "../services/api";
import { alertActionText, alertSummary, alertTypeLabel } from "../utils/alertNarration";
import { formatNumber, formatRelativeTime } from "../utils/formatters";

function AlertsPage() {
  const { messages } = useLiveFeed();
  const [lowStockProducts, setLowStockProducts] = useState([]);
  const [outOfStockProducts, setOutOfStockProducts] = useState([]);
  const [isSaving, setIsSaving] = useState(false);
  const [restockDialog, setRestockDialog] = useState({
    open: false,
    product: null,
    quantity: "50",
    error: "",
  });
  const [isLoading, setIsLoading] = useState(true);
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");

  async function loadAlertsData(showLoading = true) {
    try {
      if (showLoading) {
        setIsLoading(true);
      }
      const [low, out] = await Promise.all([
        getProducts(1, { pageSize: 100, stockStatus: "low", sortBy: "stock", sortOrder: "asc" }),
        getProducts(1, { pageSize: 100, stockStatus: "out", sortBy: "stock", sortOrder: "asc" }),
      ]);
      setLowStockProducts(low.items || []);
      setOutOfStockProducts(out.items || []);
      setError("");
    } catch (loadError) {
      setError(loadError.message || "Failed to load alerts.");
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    loadAlertsData();
  }, []);

  function openRestockDialog(product) {
    setRestockDialog({
      open: true,
      product,
      quantity: String(Math.max(Number(product.stock_quantity || 0), 50)),
      error: "",
    });
  }

  function closeRestockDialog() {
    if (isSaving) {
      return;
    }
    setRestockDialog({ open: false, product: null, quantity: "50", error: "" });
  }

  async function submitRestock() {
    const product = restockDialog.product;
    if (!product) {
      return;
    }
    const quantity = Number(restockDialog.quantity);
    if (!Number.isInteger(quantity) || quantity < 0) {
      setRestockDialog((current) => ({
        ...current,
        error: "Please enter a valid non-negative whole number.",
      }));
      return;
    }
    try {
      setIsSaving(true);
      setFeedback("");
      await updateProduct(product.id, { stock_quantity: quantity });
      setFeedback(`Updated ${product.name} stock to ${quantity}.`);
      closeRestockDialog();
      await loadAlertsData(false);
    } catch (saveError) {
      setRestockDialog((current) => ({
        ...current,
        error: saveError.message || "Failed to update stock.",
      }));
    } finally {
      setIsSaving(false);
    }
  }

  const recentAlertEvents = useMemo(
    () => {
      const productMap = new Map(
        [...lowStockProducts, ...outOfStockProducts].map((product) => [product.id, product.name]),
      );
      return messages
        .filter((message) => message.type === "ALERT")
        .slice(0, 15)
        .map((message, idx) => {
          const fallbackName = productMap.get(message.data?.product_id);
          return {
            ...message,
            _id: `${message.timestamp || "alert"}-${idx}`,
            displayName: message.data?.product_name || fallbackName || `Product #${message.data?.product_id || "--"}`,
            summary: alertSummary(message, fallbackName),
            actionText: alertActionText(message),
            label: alertTypeLabel(message.data?.alert_type || "ALERT"),
          };
        });
    },
    [messages, lowStockProducts, outOfStockProducts],
  );

  if (isLoading) {
    return <LoadingPanel label="Loading alerts..." />;
  }

  if (error) {
    return <LoadingPanel label={error} />;
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2">
        <div className="panel relative overflow-hidden p-5">
          <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-warning/20 to-warning/5 text-warning" />
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="label">Low Stock Products</p>
              <p className="mt-4 value">{formatNumber(lowStockProducts.length)}</p>
              <p className="mt-2 text-sm text-muted">Products with stock between 1 and 15 units.</p>
            </div>
            <div className="rounded-2xl border border-line/70 bg-slate-950/[0.35] p-3 text-slate-100">
              <AlertTriangle size={18} />
            </div>
          </div>
        </div>
        <div className="panel relative overflow-hidden p-5">
          <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-danger/20 to-danger/5 text-danger" />
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="label">Out Of Stock Products</p>
              <p className="mt-4 value">{formatNumber(outOfStockProducts.length)}</p>
              <p className="mt-2 text-sm text-muted">Products with stock exactly 0.</p>
            </div>
            <div className="rounded-2xl border border-line/70 bg-slate-950/[0.35] p-3 text-slate-100">
              <PackageX size={18} />
            </div>
          </div>
        </div>
      </section>

      <section className="panel p-5">
        <p className="label">Low Stock</p>
        <h3 className="mt-1 text-lg font-semibold text-slate-50">Products Requiring Attention</h3>
        {feedback ? <p className="mt-2 text-sm text-muted">{feedback}</p> : null}
        <div className="mt-4 table-shell">
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>Category</th>
                <th>Current Stock</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {lowStockProducts.map((product) => (
                <tr key={product.id}>
                  <td>
                    <div>
                      <p className="font-medium text-slate-100">{product.name}</p>
                      <p className="text-xs text-muted">#{product.id}</p>
                    </div>
                  </td>
                  <td>{product.category}</td>
                  <td className="text-warning">{formatNumber(product.stock_quantity)}</td>
                  <td>
                    <button
                      type="button"
                      className="rounded-lg border border-line/70 px-3 py-1.5 text-xs text-slate-100 disabled:opacity-50"
                      onClick={() => openRestockDialog(product)}
                      disabled={isSaving}
                    >
                      Restock
                    </button>
                  </td>
                </tr>
              ))}
              {lowStockProducts.length === 0 ? (
                <tr>
                  <td colSpan={4} className="text-center text-sm text-muted">
                    No low stock products right now.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel p-5">
        <p className="label">Out Of Stock</p>
        <h3 className="mt-1 text-lg font-semibold text-slate-50">Products Already At Zero</h3>
        <div className="mt-4 table-shell">
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>Category</th>
                <th>Current Stock</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {outOfStockProducts.map((product) => (
                <tr key={product.id}>
                  <td>
                    <div>
                      <p className="font-medium text-slate-100">{product.name}</p>
                      <p className="text-xs text-muted">#{product.id}</p>
                    </div>
                  </td>
                  <td>{product.category}</td>
                  <td className="text-danger">{formatNumber(product.stock_quantity)}</td>
                  <td>
                    <button
                      type="button"
                      className="rounded-lg border border-line/70 px-3 py-1.5 text-xs text-slate-100 disabled:opacity-50"
                      onClick={() => openRestockDialog(product)}
                      disabled={isSaving}
                    >
                      Restock
                    </button>
                  </td>
                </tr>
              ))}
              {outOfStockProducts.length === 0 ? (
                <tr>
                  <td colSpan={4} className="text-center text-sm text-muted">
                    No out-of-stock products right now.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel p-5">
        <p className="label">Recent Alert Events</p>
        <h3 className="mt-1 text-lg font-semibold text-slate-50">Latest Events From Live Feed</h3>
        <div className="mt-4 space-y-3">
          {recentAlertEvents.map((event) => (
            <div key={event._id} className="rounded-xl border border-line/70 bg-slate-950/25 px-4 py-3">
              <p className="text-sm font-medium text-slate-100">
                {event.displayName} | {event.label}
              </p>
              <p className="mt-1 text-sm text-muted">{event.summary}</p>
              {event.actionText ? <p className="mt-1 text-sm text-slate-100">Suggested action: {event.actionText}</p> : null}
              <p className="mt-2 text-xs text-muted">{formatRelativeTime(event.timestamp)}</p>
            </div>
          ))}
          {recentAlertEvents.length === 0 ? (
            <EmptyState
              title="No recent alert events"
              description="Alerts will appear here when inventory or agent services emit alert events."
            />
          ) : null}
        </div>
      </section>

      {restockDialog.open ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/70 px-4">
          <div className="panel w-full max-w-md p-5">
            <p className="label">Restock Product</p>
            <h3 className="mt-1 text-lg font-semibold text-slate-50">{restockDialog.product?.name}</h3>
            <p className="mt-2 text-sm text-muted">Enter the new stock quantity.</p>
            <label className="mt-4 block space-y-2">
              <span className="label">Stock Quantity</span>
              <input
                type="number"
                min="0"
                step="1"
                className="input-shell w-full px-3 py-2"
                value={restockDialog.quantity}
                onChange={(event) =>
                  setRestockDialog((current) => ({
                    ...current,
                    quantity: event.target.value,
                    error: "",
                  }))
                }
              />
            </label>
            {restockDialog.error ? <p className="mt-2 text-sm text-danger">{restockDialog.error}</p> : null}
            <div className="mt-5 flex items-center justify-end gap-2">
              <button
                type="button"
                className="rounded-lg border border-line/70 px-3 py-2 text-sm text-muted disabled:opacity-50"
                onClick={closeRestockDialog}
                disabled={isSaving}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-lg border border-accent/40 bg-accent/10 px-3 py-2 text-sm text-slate-100 disabled:opacity-50"
                onClick={submitRestock}
                disabled={isSaving}
              >
                {isSaving ? "Saving..." : "Update Stock"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export default AlertsPage;
