import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  Bot,
  CircleDot,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { formatCurrency, formatRelativeTime, sentenceCase } from "../utils/formatters";

function resolveProductName(message) {
  return (
    message?.data?.product_name ||
    message?.data?.name ||
    (message?.data?.product_id ? `Product #${message.data.product_id}` : "System event")
  );
}

function eventSummary(message) {
  if (!message?.type) {
    return "Unknown event";
  }

  if (message.type === "CONNECTED") {
    return `Subscribed to ${message.data?.rooms?.join(", ") || "live feed"}`;
  }

  if (message.type === "PRICE_CHANGE") {
    return `Price ${Number(message.data?.change_percent || 0) < 0 ? "dropped" : "moved"} from ${formatCurrency(message.data?.old_price)} to ${formatCurrency(message.data?.new_price)}`;
  }

  if (message.type === "AGENT_DECISION") {
    return sentenceCase(message.data?.decision_type || "Agent decision");
  }

  if (message.type === "ALERT") {
    return message.data?.reason || message.data?.alert_type || "Alert emitted";
  }

  return sentenceCase(message.type);
}

function eventMeta(message) {
  if (message?.type === "PRICE_CHANGE") {
    return message.data?.competitor_name || "Competitor price change";
  }
  if (message?.type === "AGENT_DECISION") {
    return "Agent decision";
  }
  if (message?.type === "ALERT") {
    return "Active alert";
  }
  return sentenceCase(message?.type || "Event");
}

function eventVisual(message) {
  if (message?.type === "ALERT") {
    return {
      icon: AlertTriangle,
      iconClass: "text-warning",
      shellClass: "bg-warning/10 border-warning/25",
    };
  }

  if (message?.type === "AGENT_DECISION") {
    return {
      icon: Bot,
      iconClass: "text-accent",
      shellClass: "bg-accent/10 border-accent/25",
    };
  }

  if (message?.type === "PRICE_CHANGE") {
    const isDrop = Number(message?.data?.change_percent || 0) < 0;
    return isDrop
      ? {
          icon: ArrowDownRight,
          iconClass: "text-danger",
          shellClass: "bg-danger/10 border-danger/25",
        }
      : {
          icon: ArrowUpRight,
          iconClass: "text-success",
          shellClass: "bg-success/10 border-success/25",
        };
  }

  return {
    icon: CircleDot,
    iconClass: "text-accent",
    shellClass: "bg-accent/10 border-accent/25",
  };
}

function LiveEventFeed({ messages }) {
  const [isPaused, setIsPaused] = useState(false);
  const containerRef = useRef(null);
  const previousFirstRef = useRef(messages[0]?.timestamp);
  const visibleMessages = useMemo(() => messages.slice(0, 50), [messages]);

  useEffect(() => {
    const currentFirst = visibleMessages[0]?.timestamp;
    if (!containerRef.current || !currentFirst || isPaused) {
      previousFirstRef.current = currentFirst;
      return;
    }

    if (currentFirst !== previousFirstRef.current) {
      containerRef.current.scrollTo({ top: 0, behavior: "smooth" });
    }

    previousFirstRef.current = currentFirst;
  }, [visibleMessages, isPaused]);

  return (
    <div className="panel flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-line/70 px-5 py-4">
        <div>
          <p className="label">Live Activity</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-50">Recent Event Stream</h3>
        </div>
        <span className="text-xs text-muted">{visibleMessages.length} visible</span>
      </div>

      <div
        ref={containerRef}
        className="max-h-[34rem] space-y-3 overflow-y-auto px-5 py-4"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
      >
        {visibleMessages.length === 0 ? (
          <p className="text-sm text-muted">Waiting for websocket events from the live feed.</p>
        ) : null}
        {visibleMessages.map((message, index) => {
          const visual = eventVisual(message);
          const Icon = visual.icon;

          return (
            <div key={`${message.timestamp || "event"}-${index}`} className="panel-soft feed-event-enter p-4">
              <div className="flex items-start gap-4">
                <div className={`rounded-2xl border p-3 ${visual.shellClass}`}>
                  <Icon size={18} className={visual.iconClass} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-50">{resolveProductName(message)}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.18em] text-muted">{eventMeta(message)}</p>
                    </div>
                    <span className="whitespace-nowrap text-xs text-muted">{formatRelativeTime(message.timestamp)}</span>
                  </div>
                  <p className="mt-3 text-sm text-slate-100">{eventSummary(message)}</p>
                  {message.data?.reasoning ? (
                    <p className="mt-2 max-h-16 overflow-hidden text-xs leading-6 text-muted">{message.data.reasoning}</p>
                  ) : null}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default LiveEventFeed;
