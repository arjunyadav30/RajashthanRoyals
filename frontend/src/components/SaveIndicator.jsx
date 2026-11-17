import { cx } from "../utils";

export default function SaveIndicator({ state, className }) {
  if (!state) return null;
  const label =
    state === "saving" ? "Saving…" : state === "saved" ? "Saved" : "Error";
  return (
    <span
      role="status"
      aria-live="polite"
      className={cx(
        "inline-flex items-center gap-1 text-[11px] font-semibold",
        state === "saving" && "text-slate-500 dark:text-slate-400",
        state === "saved" && "text-emerald-700 dark:text-emerald-400",
        state === "error" && "text-red-600 dark:text-red-400",
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cx(
          "h-1.5 w-1.5 rounded-full",
          state === "saving" && "animate-pulse bg-slate-400",
          state === "saved" && "bg-emerald-500",
          state === "error" && "bg-red-500",
        )}
      />
      {label}
    </span>
  );
}
