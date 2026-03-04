function SummaryCard({ label, value, hint, tone = "accent", icon: Icon }) {
  const toneClasses = {
    accent: "from-accent/20 to-accent/5 text-accent",
    success: "from-success/20 to-success/5 text-success",
    warning: "from-warning/20 to-warning/5 text-warning",
    danger: "from-danger/20 to-danger/5 text-danger",
  };

  return (
    <div className="panel relative overflow-hidden p-5">
      <div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${toneClasses[tone]}`} />
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="label">{label}</p>
          <p className="mt-4 value">{value}</p>
          <p className="mt-2 text-sm text-muted">{hint}</p>
        </div>
        {Icon ? (
          <div className="rounded-2xl border border-line/70 bg-slate-950/[0.35] p-3 text-slate-100">
            <Icon size={18} />
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default SummaryCard;
