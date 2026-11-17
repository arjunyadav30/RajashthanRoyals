import { cx } from "../utils";

export function LoadingBlock({ rows = 5, className }) {
  return (
    <div className={cx("card animate-pulse p-5", className)} aria-busy="true" aria-live="polite">
      <div className="h-4 w-40 rounded bg-slate-200 dark:bg-slate-800" />
      <div className="mt-4 space-y-3">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-slate-100 dark:bg-slate-800" />
            <div className="h-3 flex-1 rounded bg-slate-100 dark:bg-slate-800" />
            <div className="h-3 w-16 rounded bg-slate-100 dark:bg-slate-800" />
          </div>
        ))}
      </div>
      <span className="sr-only">Loading data</span>
    </div>
  );
}

export function ErrorNote({ message, onRetry, className }) {
  return (
    <div
      role="alert"
      className={cx(
        "card border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900/60 dark:bg-red-950/40 dark:text-red-200",
        className,
      )}
    >
      <p className="font-semibold">Something went wrong</p>
      <p className="mt-1 leading-relaxed">{message}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="btn-ghost mt-3">
          Try again
        </button>
      ) : null}
    </div>
  );
}

export function ReadyBanner({ ready, message }) {
  if (ready) return null;
  return (
    <div
      role="status"
      className="card border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-700/60 dark:bg-amber-950/40 dark:text-amber-200"
    >
      <p className="font-semibold">Engine scores are not loaded</p>
      <p className="mt-1 leading-relaxed">
        {message ||
          "Run python engine/run_all.py to write data_derived/scores, then restart the API."}
      </p>
    </div>
  );
}

export function EmptyState({ title = "No rows match", hint, className }) {
  return (
    <div
      className={cx(
        "flex flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-slate-300 px-6 py-12 text-center dark:border-slate-700",
        className,
      )}
    >
      <p className="text-sm font-semibold text-slate-700 dark:text-slate-200">{title}</p>
      {hint ? (
        <p className="max-w-md text-xs leading-relaxed text-slate-500 dark:text-slate-400">{hint}</p>
      ) : null}
    </div>
  );
}
