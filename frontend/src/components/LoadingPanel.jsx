function LoadingPanel({ label = "Loading..." }) {
  return (
    <div className="panel flex min-h-48 items-center justify-center">
      <div className="flex items-center gap-3 text-muted">
        <span className="h-3 w-3 animate-pulse rounded-full bg-accent" />
        <span>{label}</span>
      </div>
    </div>
  );
}

export default LoadingPanel;
