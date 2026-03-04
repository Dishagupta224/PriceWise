import { AlertTriangle, Boxes, Percent, ReceiptText } from "lucide-react";
import { useEffect, useState } from "react";
import LiveEventFeed from "../components/LiveEventFeed";
import LoadingPanel from "../components/LoadingPanel";
import SummaryCard from "../components/SummaryCard";
import TopMoversTable from "../components/TopMoversTable";
import { useLiveFeed } from "../context/LiveFeedContext";
import { getAnalyticsSummary, getTopMovers } from "../services/api";
import { formatCurrency, formatNumber, formatPercent } from "../utils/formatters";

function DashboardPage() {
  const { messages } = useLiveFeed();
  const [summary, setSummary] = useState(null);
  const [movers, setMovers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadSummary() {
      try {
        const summaryData = await getAnalyticsSummary();
        if (!isMounted) {
          return;
        }
        setSummary(summaryData);
        setError("");
      } catch (loadError) {
        if (isMounted) {
          setError(loadError.message || "Failed to load dashboard data.");
        }
      }
    }

    async function loadMovers() {
      try {
        const moversData = await getTopMovers();
        if (isMounted) {
          setMovers(moversData.items || []);
        }
      } catch (loadError) {
        if (isMounted) {
          setError(loadError.message || "Failed to load dashboard data.");
        }
      }
    }

    async function loadInitial() {
      try {
        setIsLoading(true);
        await Promise.all([loadSummary(), loadMovers()]);
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadInitial();
    const summaryInterval = window.setInterval(loadSummary, 30000);
    const moversInterval = window.setInterval(loadMovers, 60000);

    return () => {
      isMounted = false;
      window.clearInterval(summaryInterval);
      window.clearInterval(moversInterval);
    };
  }, []);

  const marginTone =
    Number(summary?.avg_margin_percent || 0) > 25
      ? "success"
      : Number(summary?.avg_margin_percent || 0) >= 20
        ? "warning"
        : "danger";

  const alertCount = Number(summary?.low_stock_products || 0);

  if (isLoading) {
    return <LoadingPanel label="Loading dashboard metrics..." />;
  }

  if (error) {
    return <LoadingPanel label={error} />;
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <SummaryCard
          label="Total Active Products"
          value={formatNumber(summary?.total_active_products)}
          hint="Active catalog items monitored by the agent"
          tone="accent"
          icon={Boxes}
        />
        <SummaryCard
          label="Decisions Made Today"
          value={formatNumber(summary?.total_decisions_today)}
          hint="Agent decisions executed in the current UTC day"
          tone="success"
          icon={ReceiptText}
        />
        <SummaryCard
          label="Average Margin"
          value={formatPercent(summary?.avg_margin_percent)}
          hint={`Net price impact ${formatCurrency(summary?.total_revenue_impact)}`}
          tone={marginTone}
          icon={Percent}
        />
        <SummaryCard
          label="Active Alerts"
          value={formatNumber(alertCount)}
          hint={`${formatNumber(summary?.overpriced_products)} overpriced products still need attention`}
          tone={alertCount > 0 ? "danger" : "success"}
          icon={AlertTriangle}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <LiveEventFeed messages={messages} />
        <TopMoversTable items={movers} />
      </section>
    </div>
  );
}

export default DashboardPage;
