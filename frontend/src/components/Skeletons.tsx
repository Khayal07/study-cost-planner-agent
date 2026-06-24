/** Shimmer placeholders shown while a plan is being computed. */
export function ResultsSkeleton() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Loading results">
      <div className="flex items-center justify-between">
        <div className="skeleton h-7 w-40" />
        <div className="skeleton h-9 w-32" />
      </div>
      <div className="card p-4">
        <div className="skeleton mb-3 h-4 w-56" />
        <div className="skeleton h-[220px] w-full rounded-xl" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="card space-y-3 p-4">
            <div className="flex justify-between">
              <div className="skeleton h-4 w-10" />
              <div className="skeleton h-5 w-24 rounded-full" />
            </div>
            <div className="skeleton h-4 w-3/4" />
            <div className="skeleton h-3 w-1/2" />
            <div className="skeleton h-4 w-full" />
          </div>
        ))}
      </div>
      <div className="card space-y-3 p-4">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="flex items-center justify-between">
            <div className="skeleton h-4 w-32" />
            <div className="skeleton h-4 w-20" />
          </div>
        ))}
      </div>
    </div>
  );
}
