import { cx, fmtNum, isNumber, rangePercent } from "../utils";

export default function ScoreRangeBar({
  score,
  lo,
  hi,
  domainMin = 0,
  domainMax = 100,
  height = 10,
  className,
}) {
  const hasInterval = isNumber(lo) && isNumber(hi) && hi >= lo;
  const loPct = rangePercent(hasInterval ? lo : score, domainMin, domainMax);
  const hiPct = rangePercent(hasInterval ? hi : score, domainMin, domainMax);
  const scorePct = rangePercent(score, domainMin, domainMax);

  return (
    <div className={className}>
      <div className="relative" style={{ height: height + 12 }}>
        <div
          className="absolute inset-x-0 rounded-full bg-slate-200 dark:bg-slate-800"
          style={{ top: 6, height }}
        />
        {hasInterval ? (
          <div
            className="absolute rounded-full bg-gradient-to-r from-sky-400/80 to-rr-500/80"
            style={{ left: `${loPct}%`, width: `${Math.max(hiPct - loPct, 1)}%`, top: 6, height }}
          />
        ) : (
          <div
            className="absolute rounded-full bg-rr-400/60"
            style={{ left: `${Math.max(scorePct - 2, 0)}%`, width: "4%", top: 6, height }}
          />
        )}
        {isNumber(score) ? (
          <div
            className="absolute z-10 h-[18px] w-[3px] -translate-x-1/2 rounded-full bg-slate-900 shadow ring-2 ring-white dark:bg-white dark:ring-slate-900"
            style={{ left: `${scorePct}%`, top: 2 }}
            title={`Score ${fmtNum(score)}`}
          />
        ) : null}
      </div>
      <div className="mt-1 flex justify-between text-[10px] font-medium text-slate-500 dark:text-slate-400">
        <span className="num">{hasInterval ? fmtNum(lo) : "—"}</span>
        <span className="num font-semibold text-slate-700 dark:text-slate-200">
          {isNumber(score) ? fmtNum(score) : "—"}
        </span>
        <span className="num">{hasInterval ? fmtNum(hi) : "—"}</span>
      </div>
      <p className={cx("mt-1 text-[10px]", "text-slate-400 dark:text-slate-500")}>
        90% interval{hasInterval ? "" : " not supplied"}
      </p>
    </div>
  );
}
