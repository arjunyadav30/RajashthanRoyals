import { cx } from "../utils";

export default function StatCard({ label, value, hint, accent = "slate", className }) {
  const accentBar = {
    slate: "bg-slate-300 dark:bg-slate-700",
    pink: "bg-rr-500",
    sky: "bg-sky-500",
    emerald: "bg-emerald-500",
    amber: "bg-amber-500",
  }[accent];

  return (
    <div className={cx("card relative overflow-hidden p-4", className)}>
      <span className={cx("absolute inset-y-0 left-0 w-1", accentBar)} />
      <p className="label">{label}</p>
      <p className="num mt-1.5 text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
        {value}
      </p>
      {hint ? (
        <p className="mt-1 text-xs leading-snug text-slate-500 dark:text-slate-400">{hint}</p>
      ) : null}
    </div>
  );
}
