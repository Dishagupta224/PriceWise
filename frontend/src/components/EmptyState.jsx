function EmptyState({ title, description }) {
  return (
    <div className="panel flex min-h-48 flex-col items-center justify-center px-6 py-10 text-center">
      <p className="text-lg font-medium text-slate-100">{title}</p>
      <p className="mt-2 max-w-md text-sm text-muted">{description}</p>
    </div>
  );
}

export default EmptyState;
