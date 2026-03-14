import { Fragment, useEffect, useMemo, useState } from "react";
import { Check, ChevronDown, ChevronLeft, ChevronRight, ChevronUp } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import EmptyState from "../components/EmptyState";
import LoadingPanel from "../components/LoadingPanel";
import StatusBadge from "../components/StatusBadge";
import { getDecision, getDecisions, getProducts } from "../services/api";
import { simplifyReasoningText, splitReasoning, summarizeHumanInterventionReason } from "../utils/decisionNarration";
import { compactDateTime, formatCurrency, formatPercent, formatRelativeTime } from "../utils/formatters";

const DECISION_TYPES = ["PRICE_DROP", "PRICE_HOLD", "PRICE_INCREASE", "REORDER_ALERT"];
const DATE_RANGES = {
  today: 0,
  last7: 7,
  last30: 30,
};

function confidenceTone(confidence) {
  if (confidence >= 0.8) {
    return "bg-success";
  }
  if (confidence >= 0.5) {
    return "bg-warning";
  }
  return "bg-danger";
}

function decisionTone(value) {
  return {
    PRICE_DROP: "border-danger/30 bg-danger/10 text-danger",
    PRICE_HOLD: "border-line/80 bg-slate-800/60 text-slate-200",
    PRICE_INCREASE: "border-success/30 bg-success/10 text-success",
    REORDER_ALERT: "border-warning/30 bg-warning/10 text-warning",
  }[value] || "border-line/80 bg-slate-900/40 text-slate-200";
}

function decisionTypeLabel(value) {
  return {
    PRICE_DROP: "Price Drop",
    PRICE_HOLD: "Price Hold",
    PRICE_INCREASE: "Price Increase",
    REORDER_ALERT: "Restock Recommended",
  }[value] || String(value || "").replace(/_/g, " ");
}

function getDateFrom(range) {
  const now = new Date();
  if (range === "today") {
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    return start.toISOString();
  }
  if (range === "last7") {
    return new Date(now.getTime() - DATE_RANGES.last7 * 24 * 60 * 60 * 1000).toISOString();
  }
  if (range === "last30") {
    return new Date(now.getTime() - DATE_RANGES.last30 * 24 * 60 * 60 * 1000).toISOString();
  }
  return undefined;
}

function toolLabel(tool) {
  return String(tool || "")
    .replace(/^get_/, "")
    .replace(/^update_/, "")
    .replace(/_/g, " ");
}

function confidenceText(confidence) {
  if (confidence >= 0.8) {
    return "High";
  }
  if (confidence >= 0.5) {
    return "Medium";
  }
  return "Low";
}

function initials(name) {
  return String(name || "P")
    .split(" ")
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");
}

function DecisionsPage() {
  const [searchParams] = useSearchParams();
  const dateRangeParam = searchParams.get("dateRange");
  const initialDateRange = ["today", "last7", "last30"].includes(dateRangeParam || "") ? dateRangeParam : "last7";
  const [response, setResponse] = useState(null);
  const [details, setDetails] = useState({});
  const [expanded, setExpanded] = useState({});
  const [productOptions, setProductOptions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({
    decisionTypes: DECISION_TYPES,
    dateRange: initialDateRange,
    productSearch: "",
    selectedProductId: "",
    minConfidence: 0,
  });

  useEffect(() => {
    let isMounted = true;

    async function loadProductOptions() {
      const productsData = await getProducts(1, {
        pageSize: 100,
        sortBy: "name",
        sortOrder: "asc",
      });
      if (isMounted) {
        setProductOptions(productsData.items || []);
      }
    }

    loadProductOptions();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        setIsLoading(true);
        const data = await getDecisions(page, {
          pageSize: 20,
          dateFrom: getDateFrom(filters.dateRange),
          productId: filters.selectedProductId || undefined,
        });

        if (!isMounted) {
          return;
        }

        const filteredItems = (data.items || []).filter((item) => {
          const matchesDecisionType = filters.decisionTypes.includes(item.decision_type);
          const matchesConfidence = Number(item.confidence_score || 0) >= Number(filters.minConfidence);
          const matchesSearch = filters.productSearch
            ? item.product_name.toLowerCase().includes(filters.productSearch.toLowerCase())
            : true;
          return matchesDecisionType && matchesConfidence && matchesSearch;
        });

        setResponse({
          ...data,
          items: filteredItems,
        });
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

  const suggestions = useMemo(() => {
    if (!filters.productSearch) {
      return productOptions.slice(0, 8);
    }

    return productOptions
      .filter((product) => product.name.toLowerCase().includes(filters.productSearch.toLowerCase()))
      .slice(0, 8);
  }, [productOptions, filters.productSearch]);

  async function toggleRow(decisionId) {
    setExpanded((current) => ({ ...current, [decisionId]: !current[decisionId] }));
    if (details[decisionId]) {
      return;
    }

    const detail = await getDecision(decisionId);
    setDetails((current) => ({ ...current, [decisionId]: detail }));
  }

  function toggleDecisionType(type) {
    setPage(1);
    setFilters((current) => {
      const exists = current.decisionTypes.includes(type);
      return {
        ...current,
        decisionTypes: exists
          ? current.decisionTypes.filter((item) => item !== type)
          : [...current.decisionTypes, type],
      };
    });
  }

  if (isLoading && !response) {
    return <LoadingPanel label="Loading decisions..." />;
  }

  const decisions = response?.items || [];
  const pagination = response?.pagination;

  return (
    <div className="space-y-6">
      <section className="panel p-5">
        <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
          <div className="space-y-4">
            <div>
              <p className="label">Decision Type</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {DECISION_TYPES.map((type) => {
                  const active = filters.decisionTypes.includes(type);
                  return (
                    <button
                      key={type}
                      type="button"
                      onClick={() => toggleDecisionType(type)}
                      className={`inline-flex items-center gap-2 rounded-full border px-4 py-2.5 text-sm transition ${
                        active ? decisionTone(type) : "border-line/70 bg-slate-950/[0.30] text-muted"
                      }`}
                    >
                      <span
                        className={`grid h-4 w-4 place-items-center rounded-full border ${
                          active
                            ? "border-fuchsia-400 bg-fuchsia-500 text-white"
                            : "border-line/70 bg-transparent text-transparent"
                        }`}
                      >
                        <Check size={10} strokeWidth={3} />
                      </span>
                      <span>{decisionTypeLabel(type)}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <p className="label">Product Search</p>
              <div className="relative mt-3">
                <input
                  className="input-shell h-10 w-full px-4"
                  value={filters.productSearch}
                  placeholder="Search by product name..."
                  onChange={(event) => {
                    setPage(1);
                    setFilters((current) => ({
                      ...current,
                      productSearch: event.target.value,
                      selectedProductId: "",
                    }));
                  }}
                />
                {filters.productSearch.length >= 2 ? (
                  <div className="absolute left-0 right-0 top-[calc(100%+0.5rem)] z-10 max-h-64 overflow-y-auto rounded-2xl border border-line/70 bg-panel p-2 shadow-panel">
                    {suggestions.length === 0 ? (
                      <p className="px-3 py-2 text-sm text-muted">No matching products.</p>
                    ) : (
                      suggestions.map((product) => (
                        <button
                          key={product.id}
                          type="button"
                          className="flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm text-slate-100 transition hover:bg-white/5"
                          onClick={() => {
                            setPage(1);
                            setFilters((current) => ({
                              ...current,
                              productSearch: product.name,
                              selectedProductId: product.id,
                            }));
                          }}
                        >
                          <span>{product.name}</span>
                          <span className="text-xs text-muted">#{product.id}</span>
                        </button>
                      ))
                    )}
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2">
              <span className="label">Date Range</span>
              <select
                className="input-shell w-full"
                value={filters.dateRange}
                onChange={(event) => {
                  setPage(1);
                  setFilters((current) => ({ ...current, dateRange: event.target.value }));
                }}
              >
                <option value="today">Today</option>
                <option value="last7">Last 7 days</option>
                <option value="last30">Last 30 days</option>
              </select>
            </label>

            <div className="space-y-2">
              <span className="label">Confidence Threshold</span>
              <div className="panel-soft px-4 py-3">
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={filters.minConfidence}
                  onChange={(event) => {
                    setPage(1);
                    setFilters((current) => ({ ...current, minConfidence: Number(event.target.value) }));
                  }}
                  className="w-full accent-cyan-400"
                />
                <div className="mt-2 flex items-center justify-between text-sm">
                  <span className="text-muted">Minimum confidence</span>
                  <span className="font-medium text-slate-100">{formatPercent(filters.minConfidence * 100)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {decisions.length === 0 ? (
        <EmptyState
          title="No decisions matched the filters"
          description="Broaden the filters or load a different date range to inspect more agent decisions."
        />
      ) : (
        <section className="space-y-4">
          {decisions.map((decision) => {
            const detail = details[decision.id];
            const isExpanded = Boolean(expanded[decision.id]);
            const confidence = Number(decision.confidence_score || 0);
            const displayReasoning = simplifyReasoningText(detail?.reasoning || decision.reasoning_preview);
            const steps = splitReasoning(detail?.reasoning || decision.reasoning_preview);
            const rejectionReason = summarizeHumanInterventionReason(detail?.reasoning || decision.reasoning_preview);
            const beforePrice = Number(detail?.before_price ?? 0);
            const afterPrice = Number(detail?.after_price ?? 0);
            const delta = beforePrice > 0 && afterPrice > 0 ? afterPrice - beforePrice : 0;
            const deltaPercent = beforePrice > 0 ? (delta / beforePrice) * 100 : 0;

            return (
              <div key={decision.id} className="panel overflow-hidden">
                <div className="px-5 py-5">
                  <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_15rem]">
                    <button
                      type="button"
                      className="flex w-full items-start gap-3 text-left transition hover:opacity-95"
                      onClick={() => toggleRow(decision.id)}
                    >
                      <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-line/70 bg-accent/10 text-sm font-semibold leading-none text-accent">
                        {initials(decision.product_name)}
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="pt-0.5">
                            <p className="text-sm text-muted">{formatRelativeTime(decision.created_at)}</p>
                            <h3 className="mt-1 text-lg font-semibold text-slate-50">{decision.product_name}</h3>
                            <p className="text-xs text-muted">Product #{decision.product_id}</p>
                            {decision.execution_status === "REJECTED" ? (
                              <>
                                <p className="mt-2 inline-flex rounded-full border border-warning/40 bg-warning/10 px-2 py-1 text-xs font-medium text-warning">
                                  Needs manual review
                                </p>
                                <p className="mt-2 max-w-3xl text-xs leading-6 text-warning/90">
                                  Why AI did not execute: {rejectionReason}
                                </p>
                              </>
                            ) : null}
                          </div>

                          <div className="flex items-center gap-3">
                            <span className={`status-pill ${decisionTone(decision.decision_type)}`}>
                              {decisionTypeLabel(decision.decision_type)}
                            </span>
                            <span className="rounded-xl border border-line/70 bg-slate-950/[0.30] p-2 text-slate-100">
                              {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                            </span>
                          </div>
                        </div>

                        <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-100">{displayReasoning}</p>

                        <div className="mt-4 flex flex-wrap gap-2">
                          {(detail?.tools_used || []).length > 0 ? (
                            (detail.tools_used || []).map((tool) => (
                              <span
                                key={`${decision.id}-${tool}`}
                                className="rounded-full border border-line/70 bg-slate-950/[0.35] px-3 py-1 text-xs text-slate-200"
                              >
                                {toolLabel(tool)}
                              </span>
                            ))
                          ) : (
                          <span className="mx-2 mt-1 rounded-full border border-line/70 bg-slate-950/[0.35] px-3 py-1 text-xs text-muted">
                            Tool details available on expand
                          </span>
                          )}
                        </div>
                      </div>
                    </button>

                    <div className="mx-2 my-2 panel-soft p-5">
                      <div className="flex items-center justify-between">
                        <p className="label">Confidence</p>
                        <span className="text-sm font-medium text-slate-100">{formatPercent(confidence * 100)}</span>
                      </div>
                      <div className="metric-bar mt-3">
                        <span
                          className={confidenceTone(confidence)}
                          style={{ width: `${Math.max(Math.min(confidence * 100, 100), 6)}%` }}
                        />
                      </div>
                      <p className="mt-3 text-sm text-muted">{confidenceText(confidence)} confidence</p>
                      <p className="mt-2 text-xs text-muted">{compactDateTime(decision.created_at)}</p>
                    </div>
                  </div>
                </div>

                {isExpanded ? (
                  <div className="mt-6 border-t border-line/70 bg-slate-950/20 px-7 py-7">
                    {detail ? (
                      <div className="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
                        <div className="space-y-6">
                          <div className="mx-2 my-2 panel-soft px-7 py-7">
                            <p className="label">Thought Process</p>
                            <div className="mt-5 space-y-4">
                              {steps.map((step, index) => (
                                <div key={`${decision.id}-step-${index}`} className="flex gap-3">
                                  <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent/[0.15] text-xs font-semibold text-accent">
                                    {index + 1}
                                  </div>
                                  <p className="text-sm leading-7 text-slate-100">{step}</p>
                                </div>
                              ))}
                            </div>
                          </div>

                          <div className="mx-2 my-2 panel-soft px-7 py-7">
                            <p className="label">Tool Calls</p>
                            <div className="mt-5 flex flex-wrap gap-3">
                              {(detail.tools_used || []).map((tool) => (
                                <span
                                  key={`${decision.id}-detail-${tool}`}
                                  className="rounded-full border border-line/70 bg-slate-950/[0.35] px-3 py-1 text-xs text-slate-100"
                                >
                                  {toolLabel(tool)}
                                </span>
                              ))}
                              {(detail.tools_used || []).length === 0 ? (
                                <span className="text-sm text-muted">No tool calls were persisted for this decision.</span>
                              ) : null}
                            </div>
                            <p className="mt-5 text-sm leading-7 text-muted">
                              Tool names are stored by the backend, but raw tool outputs are not persisted. This panel shows the
                              decision path the agent relied on.
                            </p>
                          </div>
                        </div>

                        <div className="space-y-6">
                          <div className="mx-2 my-2 panel-soft px-7 py-7">
                            <p className="label">Price Comparison</p>
                            <div className="mt-5 grid gap-4">
                              <div className="flex items-center justify-between rounded-xl border border-line/70 bg-slate-950/25 px-4 py-3">
                                <span className="text-sm text-muted">Before</span>
                                <span className="text-lg font-semibold text-slate-50">{formatCurrency(detail.before_price)}</span>
                              </div>
                              <div className="flex items-center justify-between rounded-xl border border-line/70 bg-slate-950/25 px-4 py-3">
                                <span className="text-sm text-muted">After</span>
                                <span className="text-lg font-semibold text-slate-50">{formatCurrency(detail.after_price)}</span>
                              </div>
                            </div>
                          </div>

                          <div className="mx-2 my-2 panel-soft px-7 py-7">
                            <p className="label">Margin Impact Analysis</p>
                            <div className="mt-5 space-y-4 text-sm">
                              <div className="flex items-center justify-between">
                                <span className="text-muted">Absolute price delta</span>
                                <span className={delta >= 0 ? "text-success" : "text-danger"}>
                                  {delta >= 0 ? "+" : ""}
                                  {formatCurrency(delta)}
                                </span>
                              </div>
                              <div className="flex items-center justify-between">
                                <span className="text-muted">Relative change</span>
                                <span className={deltaPercent >= 0 ? "text-success" : "text-danger"}>
                                  {formatPercent(deltaPercent)}
                                </span>
                              </div>
                              <div className="rounded-xl border border-line/70 bg-slate-950/25 px-4 py-3 text-muted">
                                {delta < 0
                                  ? "The agent traded margin for competitiveness by reducing the selling price."
                                  : delta > 0
                                    ? "The agent expanded price and margin headroom while staying within guardrails."
                                    : "The agent held price, so margin impact remained neutral."}
                              </div>
                            </div>
                          </div>

                          <div className="mx-2 my-2 panel-soft px-7 py-7">
                            <p className="label">Execution Snapshot</p>
                            <div className="mt-4 flex items-center justify-between">
                              <StatusBadge value={detail.execution_status} />
                              <span className="text-sm text-muted">{compactDateTime(detail.created_at)}</span>
                            </div>
                            {detail.execution_status === "REJECTED" ? (
                              <div className="mt-4 rounded-xl border border-warning/40 bg-warning/10 px-4 py-3 text-sm leading-6 text-warning">
                                <p className="font-medium">Why AI did not execute</p>
                                <p className="mt-1">{rejectionReason}</p>
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm text-muted">Loading full decision detail...</p>
                    )}
                  </div>
                ) : null}
              </div>
            );
          })}

          <div className="panel flex items-center justify-between px-5 py-4">
            <div className="text-sm text-muted">
              Page {pagination?.page || page} of {pagination?.total_pages || 1}
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

export default DecisionsPage;
