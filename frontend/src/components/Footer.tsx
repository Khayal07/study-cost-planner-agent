export function Footer() {
  return (
    <footer className="mt-20 border-t border-border">
      <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 px-4 py-8 text-sm text-muted sm:flex-row sm:items-center sm:px-6">
        <p className="max-w-md leading-relaxed">
          Figures are curated approximations grounded in cited sources and may change.
          Verify each at its source before deciding.
        </p>
        <div className="flex items-center gap-4">
          <span className="chip bg-primary-weak text-primary">teal = sourced</span>
          <span className="chip bg-accent-weak text-accent">amber = estimate</span>
        </div>
      </div>
    </footer>
  );
}
