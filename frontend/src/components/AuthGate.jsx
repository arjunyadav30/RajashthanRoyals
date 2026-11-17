import { useAuth, LockIcon } from "../auth";
import { PUBLIC_ROW_LIMIT, cx, fmtInt } from "../utils";

export function usePublicRows(rows) {
  const { authenticated } = useAuth();
  return {
    authenticated,
    visibleRows: authenticated ? rows : rows.slice(0, PUBLIC_ROW_LIMIT),
    locked: !authenticated && rows.length > PUBLIC_ROW_LIMIT,
  };
}

export function LockBanner({ shown, total, noun = "rows", className }) {
  const { openLogin } = useAuth();
  return (
    <div
      className={cx(
        "flex flex-wrap items-center gap-3 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-xs dark:border-amber-800/70 dark:bg-amber-950/30",
        className,
      )}
    >
      <LockIcon className="h-5 w-5 shrink-0 text-amber-700 dark:text-amber-400" />
      <p className="min-w-0 flex-1 leading-relaxed text-amber-900 dark:text-amber-200">
        <span className="font-semibold">Preview mode.</span> Showing {fmtInt(shown)} of{" "}
        {fmtInt(total)} {noun}. Sign in to view everything, edit and download.
      </p>
      <button type="button" className="btn-primary" onClick={openLogin}>
        Sign in
      </button>
    </div>
  );
}
