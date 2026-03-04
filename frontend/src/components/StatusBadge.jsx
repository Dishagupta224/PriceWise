import { sentenceCase } from "../utils/formatters";

const toneMap = {
  PRICE_INCREASE: "border-success/30 bg-success/10 text-success",
  PRICE_DROP: "border-warning/30 bg-warning/10 text-warning",
  PRICE_HOLD: "border-line/80 bg-slate-800/60 text-slate-200",
  REORDER_ALERT: "border-danger/30 bg-danger/10 text-danger",
  PRICE_CHANGE: "border-accent/30 bg-accent/10 text-accent",
  CONNECTED: "border-accent/30 bg-accent/10 text-accent",
  ALERT: "border-danger/30 bg-danger/10 text-danger",
  EXECUTED: "border-success/30 bg-success/10 text-success",
  REJECTED: "border-danger/30 bg-danger/10 text-danger",
  PENDING: "border-warning/30 bg-warning/10 text-warning",
};

function StatusBadge({ value }) {
  return (
    <span className={`status-pill ${toneMap[value] || "border-line/80 bg-slate-900/50 text-slate-200"}`}>
      {sentenceCase(value)}
    </span>
  );
}

export default StatusBadge;
