import type { Citation } from "@/lib/api";

export function CitationChip({
  citation,
  confidence,
}: {
  citation: Citation;
  confidence?: string;
}) {
  const isEstimate = confidence === "estimate" || citation.source_type === "estimate";
  const badge = isEstimate
    ? "bg-accent-weak text-accent"
    : "bg-primary-weak text-primary";
  const label = isEstimate ? "estimate" : "sourced";

  const body = (
    <span className="inline-flex max-w-full items-center gap-1.5 rounded-full border border-border bg-surface px-2 py-0.5 text-[11px] text-muted transition-colors hover:border-primary/40 hover:text-foreground">
      <span className={`rounded-full px-1.5 py-px text-[10px] font-semibold ${badge}`}>{label}</span>
      <span className="max-w-[150px] truncate">{citation.publisher}</span>
      {citation.url && (
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-primary" aria-hidden="true">
          <path d="M7 17 17 7M9 7h8v8" />
        </svg>
      )}
    </span>
  );

  if (!citation.url) return body;
  return (
    <a
      href={citation.url}
      target="_blank"
      rel="noopener noreferrer"
      title={citation.url}
      className="inline-flex max-w-full rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
    >
      {body}
    </a>
  );
}
