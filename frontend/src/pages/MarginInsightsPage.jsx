import { AlertTriangle, IndianRupee, Percent, TrendingUp } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import LoadingPanel from "../components/LoadingPanel";
import { getProducts } from "../services/api";
import { formatCurrency, formatNumber, formatPercent } from "../utils/formatters";

function InsightCard({ label, value, hint, icon: Icon, tone = "accent", onClick, active = false }) {
  const toneClasses = {
    accent: "from-accent/20 to-accent/5 text-accent",
    success: "from-success/20 to-success/5 text-success",
    warning: "from-warning/20 to-warning/5 text-warning",
    danger: "from-danger/20 to-danger/5 text-danger",
  };

  return (
    <button
      type="button"
      className={`panel relative w-full overflow-hidden p-5 text-left ${onClick ? "transition hover:border-line hover:bg-white/[0.02]" : ""} ${active ? "border-accent/40" : ""}`}
      onClick={onClick}
      disabled={!onClick}
    >
      <div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${toneClasses[tone]}`} />
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="label">{label}</p>
          <p className="mt-4 value">{value}</p>
          <p className="mt-2 text-sm text-muted">{hint}</p>
        </div>
        <div className="rounded-2xl border border-line/70 bg-slate-950/[0.35] p-3 text-slate-100">
          <Icon size={18} />
        </div>
      </div>
    </button>
  );
}

function MarginInsightsPage() {
  const [products, setProducts] = useState([]);
  const [filterMode, setFilterMode] = useState("all");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadProducts() {
      try {
        setIsLoading(true);
        const data = await getProducts(1, {
          pageSize: 100,
          sortBy: "name",
          sortOrder: "asc",
        });
        if (!isMounted) {
          return;
        }
        setProducts(data.items || []);
        setError("");
      } catch (loadError) {
        if (isMounted) {
          setError(loadError.message || "Failed to load margin insights.");
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadProducts();
    return () => {
      isMounted = false;
    };
  }, []);

  const analysis = useMemo(() => {
    const activeProducts = products.filter((item) => item.is_active);
    if (activeProducts.length === 0) {
      return {
        activeCount: 0,
        avgMargin: 0,
        avgUnitProfit: 0,
        belowTargetCount: 0,
        tightCushionCount: 0,
        rows: [],
        lowestCushionRows: [],
      };
    }

    const rows = activeProducts.map((item) => {
      const currentMargin = Number(item.current_margin_percent || 0);
      const minMargin = Number(item.min_margin_percent || 0);
      const marginCushion = currentMargin - minMargin;
      const unitProfit = Number(item.our_price) - Number(item.cost_price);
      return {
        ...item,
        currentMargin,
        minMargin,
        marginCushion,
        unitProfit,
      };
    });

    const avgMargin = rows.reduce((sum, row) => sum + row.currentMargin, 0) / rows.length;
    const avgUnitProfit = rows.reduce((sum, row) => sum + row.unitProfit, 0) / rows.length;
    const belowTargetCount = rows.filter((row) => row.currentMargin < row.minMargin).length;
    const tightCushionCount = rows.filter((row) => row.marginCushion <= 3).length;
    const lowestCushionRows = [...rows]
      .sort((left, right) => left.marginCushion - right.marginCushion)
      .slice(0, 12);

    return {
      activeCount: rows.length,
      avgMargin,
      avgUnitProfit,
      belowTargetCount,
      tightCushionCount,
      rows,
      lowestCushionRows,
    };
  }, [products]);

  const filteredRows = useMemo(() => {
    if (filterMode === "below") {
      return analysis.rows.filter((row) => row.marginCushion < 0).sort((a, b) => a.marginCushion - b.marginCushion);
    }
    if (filterMode === "tight") {
      return analysis.rows.filter((row) => row.marginCushion >= 0 && row.marginCushion <= 3).sort((a, b) => a.marginCushion - b.marginCushion);
    }
    if (filterMode === "healthy") {
      return analysis.rows.filter((row) => row.marginCushion > 3).sort((a, b) => a.marginCushion - b.marginCushion);
    }
    return analysis.lowestCushionRows;
  }, [analysis.lowestCushionRows, analysis.rows, filterMode]);

  if (isLoading) {
    return <LoadingPanel label="Loading margin insights..." />;
  }

  if (error) {
    return <LoadingPanel label={error} />;
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <InsightCard
          label="Average Margin"
          value={formatPercent(analysis.avgMargin)}
          hint={`${formatNumber(analysis.activeCount)} active products analyzed. Cushion = current margin - minimum margin.`}
          icon={Percent}
          tone="accent"
          onClick={() => setFilterMode("all")}
          active={filterMode === "all"}
        />
        <InsightCard
          label="Average Unit Profit"
          value={formatCurrency(analysis.avgUnitProfit)}
          hint="Mean per-unit spread between sell price and cost"
          icon={IndianRupee}
          tone="success"
          onClick={() => setFilterMode("healthy")}
          active={filterMode === "healthy"}
        />
        <InsightCard
          label="Below Margin Target"
          value={formatNumber(analysis.belowTargetCount)}
          hint="Click to view products where current margin is below configured minimum."
          icon={AlertTriangle}
          tone={analysis.belowTargetCount > 0 ? "danger" : "success"}
          onClick={() => setFilterMode("below")}
          active={filterMode === "below"}
        />
        <InsightCard
          label="Tight Cushion (<=3%)"
          value={formatNumber(analysis.tightCushionCount)}
          hint="Click to view products near their minimum margin floor."
          icon={TrendingUp}
          tone={analysis.tightCushionCount > 0 ? "warning" : "success"}
          onClick={() => setFilterMode("tight")}
          active={filterMode === "tight"}
        />
      </section>

      <section className="panel p-5">
        <div className="mb-4">
          <p className="label">Margin Risk</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-50">
            {filterMode === "below"
              ? "Below Margin Target Products"
              : filterMode === "tight"
                ? "Tight Cushion Products (<=3%)"
                : filterMode === "healthy"
                  ? "Healthy Margin Cushion Products (>3%)"
                  : "Lowest Margin Cushion Products"}
          </h3>
          <p className="mt-2 text-sm text-muted">
            Cushion means: <strong>current margin % - minimum margin %</strong>. Negative cushion means the product is below its margin target.
          </p>
        </div>
        <div className="mb-4 flex flex-wrap gap-2">
          <button
            type="button"
            className={`rounded-full border px-3 py-1.5 text-xs ${filterMode === "all" ? "border-accent/40 bg-accent/10 text-slate-100" : "border-line/70 text-muted"}`}
            onClick={() => setFilterMode("all")}
          >
            Lowest 12
          </button>
          <button
            type="button"
            className={`rounded-full border px-3 py-1.5 text-xs ${filterMode === "below" ? "border-danger/40 bg-danger/10 text-slate-100" : "border-line/70 text-muted"}`}
            onClick={() => setFilterMode("below")}
          >
            Below Target
          </button>
          <button
            type="button"
            className={`rounded-full border px-3 py-1.5 text-xs ${filterMode === "tight" ? "border-warning/40 bg-warning/10 text-slate-100" : "border-line/70 text-muted"}`}
            onClick={() => setFilterMode("tight")}
          >
            Tight (0 to 3%)
          </button>
          <button
            type="button"
            className={`rounded-full border px-3 py-1.5 text-xs ${filterMode === "healthy" ? "border-success/40 bg-success/10 text-slate-100" : "border-line/70 text-muted"}`}
            onClick={() => setFilterMode("healthy")}
          >
            Healthy ({">"}3%)
          </button>
        </div>
        <div className="table-shell">
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>Category</th>
                <th>Current Margin</th>
                <th>Minimum Margin</th>
                <th>Cushion</th>
                <th>Unit Profit</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <div>
                      <p className="font-medium text-slate-100">{row.name}</p>
                      <p className="text-xs text-muted">#{row.id}</p>
                    </div>
                  </td>
                  <td>{row.category}</td>
                  <td>{formatPercent(row.currentMargin)}</td>
                  <td>{formatPercent(row.minMargin)}</td>
                  <td className={row.marginCushion <= 0 ? "text-danger" : row.marginCushion <= 3 ? "text-warning" : "text-success"}>
                    {formatPercent(row.marginCushion)}
                  </td>
                  <td>{formatCurrency(row.unitProfit)}</td>
                </tr>
              ))}
              {filteredRows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center text-sm text-muted">
                    No products found for this filter.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

export default MarginInsightsPage;
