import { Fragment, useEffect, useMemo, useState } from "react";
import { ArrowLeft, ChevronDown, ChevronUp } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import EmptyState from "../components/EmptyState";
import LoadingPanel from "../components/LoadingPanel";
import ProductPriceChart from "../components/ProductPriceChart";
import StatusBadge from "../components/StatusBadge";
import useWebSocket from "../hooks/useWebSocket";
import { getDecision, getDecisions, getProduct, getProductPriceHistory } from "../services/api";
import { compactDateTime, formatCurrency, formatPercent, formatNumber, stockTone } from "../utils/formatters";

function buildProductWebSocketUrl(productId) {
  const configuredBase = import.meta.env.VITE_WS_BASE_URL;
  if (configuredBase) {
    return `${configuredBase.replace(/\/+$/, "")}/ws/product/${productId}`;
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location.hostname || "localhost";
  return `${protocol}://${host}:8000/ws/product/${productId}`;
}

function ProductDetailPage() {
  const { productId } = useParams();
  const [product, setProduct] = useState(null);
  const [history, setHistory] = useState(null);
  const [historyDays, setHistoryDays] = useState(7);
  const [decisions, setDecisions] = useState([]);
  const [decisionDetails, setDecisionDetails] = useState({});
  const [expanded, setExpanded] = useState({});
  const [isLoading, setIsLoading] = useState(true);
  const { messages, isConnected } = useWebSocket(productId ? buildProductWebSocketUrl(productId) : "");

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        setIsLoading(true);
        const [productData, historyData, decisionsData] = await Promise.all([
          getProduct(productId),
          getProductPriceHistory(productId, historyDays),
          getDecisions(1, { pageSize: 10, productId }),
        ]);

        if (!isMounted) {
          return;
        }

        setProduct(productData);
        setHistory(historyData);
        setDecisions(decisionsData.items || []);
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
  }, [productId, historyDays]);

  useEffect(() => {
    const latestMessage = messages[0];
    if (!latestMessage || !["PRICE_CHANGE", "AGENT_DECISION", "ALERT"].includes(latestMessage.type)) {
      return;
    }

    const timer = window.setTimeout(async () => {
      const [productData, historyData, decisionsData] = await Promise.all([
        getProduct(productId),
        getProductPriceHistory(productId, historyDays),
        getDecisions(1, { pageSize: 10, productId }),
      ]);
      setProduct(productData);
      setHistory(historyData);
      setDecisions(decisionsData.items || []);
    }, 350);

    return () => window.clearTimeout(timer);
  }, [messages, productId, historyDays]);

  const stockProgress = useMemo(() => Math.min((Number(product?.stock_quantity || 0) / 100) * 100, 100), [product]);

  async function toggleDecision(decisionId) {
    setExpanded((current) => ({ ...current, [decisionId]: !current[decisionId] }));
    if (decisionDetails[decisionId]) {
      return;
    }

    const detail = await getDecision(decisionId);
    setDecisionDetails((current) => ({ ...current, [decisionId]: detail }));
  }

  if (isLoading) {
    return <LoadingPanel label="Loading product detail..." />;
  }

  if (!product) {
    return (
      <EmptyState
        title="Product not found"
        description="The selected product could not be loaded from the backend API."
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/products" className="inline-flex items-center gap-2 text-sm text-muted transition hover:text-slate-100">
            <ArrowLeft size={16} />
            Back to products
          </Link>
          <h1 className="mt-3 text-3xl font-semibold text-slate-50">{product.name}</h1>
          <p className="mt-2 text-sm text-muted">{product.category}</p>
        </div>

        <div className="panel min-w-[20rem] p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <p className="label">Current Price</p>
                <p className="mt-2 text-4xl font-semibold text-slate-50">{formatCurrency(product.our_price)}</p>
              </div>
              <div>
                <p className="label">Cost Price</p>
                <p className="mt-3 text-2xl font-semibold text-slate-200">{formatCurrency(product.cost_price)}</p>
              </div>
            </div>
            <StatusBadge value={isConnected ? "EXECUTED" : "PENDING"} />
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <div>
              <p className="label">Stock</p>
              <p className={`mt-2 text-xl font-semibold ${stockTone(product.stock_quantity)}`}>
                {formatNumber(product.stock_quantity)} units
              </p>
              <div className="metric-bar mt-3">
                <span
                  className={product.stock_quantity <= 5 ? "bg-danger" : product.stock_quantity <= 15 ? "bg-warning" : "bg-success"}
                  style={{ width: `${stockProgress}%` }}
                />
              </div>
            </div>
            <div>
              <p className="label">Margin</p>
              <p className="mt-2 text-xl font-semibold text-slate-50">{formatPercent(product.current_margin_percent)}</p>
              <p className="mt-3 text-sm text-muted">
                Best competitor {formatCurrency(product.latest_competitor_prices?.[0]?.price)}
              </p>
            </div>
          </div>
        </div>
      </div>

      <section className="panel p-5">
        <div className="mb-5 flex items-center justify-between gap-4">
          <div>
            <p className="label">Price History Chart</p>
            <h3 className="mt-1 text-lg font-semibold text-slate-50">Last {historyDays} Days</h3>
          </div>

          <label className="space-y-2">
            <span className="label">Range</span>
            <select
              className="input-shell min-w-32"
              value={historyDays}
              onChange={(event) => setHistoryDays(Number(event.target.value))}
            >
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
              <option value={30}>30 days</option>
            </select>
          </label>
        </div>
        <ProductPriceChart points={history?.points || []} />
      </section>

      <section className="panel">
        <div className="flex items-center justify-between border-b border-line/70 px-5 py-4">
          <div>
            <p className="label">Recent Decisions</p>
            <h3 className="mt-1 text-lg font-semibold text-slate-50">Last 10 Agent Decisions</h3>
          </div>
          <StatusBadge value={isConnected ? "CONNECTED" : "PENDING"} />
        </div>

        {decisions.length === 0 ? (
          <div className="px-5 py-8 text-sm text-muted">No agent decisions recorded for this product yet.</div>
        ) : (
          <div className="table-shell rounded-none border-0 bg-transparent">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Decision</th>
                  <th>Reasoning</th>
                  <th>Confidence</th>
                  <th>Expand</th>
                </tr>
              </thead>
              <tbody>
                {decisions.map((decision) => {
                  const isExpanded = Boolean(expanded[decision.id]);
                  const detail = decisionDetails[decision.id];

                  return (
                    <Fragment key={decision.id}>
                      <tr>
                        <td>{compactDateTime(decision.created_at)}</td>
                        <td><StatusBadge value={decision.decision_type} /></td>
                        <td className="max-w-xl truncate text-muted">{decision.reasoning_preview}</td>
                        <td>{formatPercent((decision.confidence_score || 0) * 100)}</td>
                        <td>
                          <button
                            type="button"
                            className="rounded-xl border border-line/70 bg-slate-900/[0.35] p-2 text-slate-100"
                            onClick={() => toggleDecision(decision.id)}
                          >
                            {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                          </button>
                        </td>
                      </tr>
                      {isExpanded ? (
                        <tr className="bg-slate-950/20">
                          <td colSpan={5}>
                            <div className="space-y-4 py-2">
                              <p className="text-sm leading-7 text-slate-100">{detail?.reasoning || decision.reasoning_preview}</p>
                              {detail ? (
                                <div className="grid gap-3 md:grid-cols-3">
                                  <div className="panel-soft p-4">
                                    <p className="label">Execution Status</p>
                                    <div className="mt-2"><StatusBadge value={detail.execution_status} /></div>
                                  </div>
                                  <div className="panel-soft p-4">
                                    <p className="label">Before Price</p>
                                    <p className="mt-2 text-lg font-semibold text-slate-50">{formatCurrency(detail.before_price)}</p>
                                  </div>
                                  <div className="panel-soft p-4">
                                    <p className="label">After Price</p>
                                    <p className="mt-2 text-lg font-semibold text-slate-50">{formatCurrency(detail.after_price)}</p>
                                  </div>
                                </div>
                              ) : (
                                <p className="text-sm text-muted">Loading full decision detail...</p>
                              )}
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default ProductDetailPage;
