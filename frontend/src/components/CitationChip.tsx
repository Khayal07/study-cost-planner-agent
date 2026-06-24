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
    ? "bg-amber-100 text-amber-700"
    : "bg-emerald-100 text-emerald-700";
  const label = isEstimate ? "estimate" : "sourced";

  const body = (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600 hover:border-brand">
      <span className={`rounded-full px-1.5 py-px text-[10px] font-medium ${badge}`}>{label}</span>
      <span className="max-w-[180px] truncate">{citation.publisher}</span>
      {citation.url && <span className="text-brand">↗</span>}
    </span>
  );

  if (!citation.url) return body;
  return (
    <a href={citation.url} target="_blank" rel="noopener noreferrer" title={citation.url}>
      {body}
    </a>
  );
}
