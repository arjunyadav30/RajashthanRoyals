import { BADGE_TONES, cx, flagBadges, initials, statusMeta } from "../utils";

export function PlayerAvatar({ name, role = "batter", size = "md" }) {
  const sizes = {
    sm: "h-7 w-7 text-[10px]",
    md: "h-9 w-9 text-xs",
    lg: "h-14 w-14 text-lg",
  };
  return (
    <span
      aria-hidden="true"
      className={cx(
        "inline-flex shrink-0 items-center justify-center rounded-full font-bold text-white ring-2 ring-white/60 dark:ring-slate-900/60",
        role === "bowler"
          ? "bg-gradient-to-br from-sky-500 to-blue-700"
          : "bg-gradient-to-br from-rr-500 to-rr-700",
        sizes[size] ?? sizes.md,
      )}
    >
      {initials(name) || "?"}
    </span>
  );
}

export function StatusPill({ status, className }) {
  const meta = statusMeta(status);
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset",
        meta.pill,
        className,
      )}
      title={meta.description}
    >
      <span className={cx("h-1.5 w-1.5 rounded-full", meta.dot)} />
      {meta.short}
    </span>
  );
}

export function FlagBadge({ label, tone = "slate", title }) {
  return (
    <span
      title={title}
      className={cx(
        "inline-flex whitespace-nowrap rounded-md px-1.5 py-0.5 text-[10px] font-bold tracking-wide ring-1 ring-inset",
        BADGE_TONES[tone] ?? BADGE_TONES.slate,
      )}
    >
      {label}
    </span>
  );
}

export function FlagBadges({ row, className }) {
  const badges = flagBadges(row);
  if (badges.length === 0) {
    return <span className="text-xs text-slate-400 dark:text-slate-500">—</span>;
  }
  return (
    <span className={cx("flex flex-wrap gap-1", className)}>
      {badges.map((badge) => (
        <FlagBadge key={badge.key} label={badge.label} tone={badge.tone} title={badge.title} />
      ))}
    </span>
  );
}

export function RankChip({ rank, tone = "default" }) {
  if (rank === null || rank === undefined) {
    return <span className="text-sm text-slate-400">—</span>;
  }
  return (
    <span
      className={cx(
        "num inline-flex h-7 min-w-[1.75rem] items-center justify-center rounded-lg px-1 text-xs font-bold",
        tone === "shortlist" &&
          "bg-rr-600 text-white shadow-sm dark:bg-rr-500",
        tone === "reserve" &&
          "bg-sky-100 text-sky-800 dark:bg-sky-500/20 dark:text-sky-300",
        tone === "default" &&
          "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
      )}
    >
      {rank}
    </span>
  );
}

export function AvailabilityBadge({ row }) {
  if (row?.available) return null;
  return <StatusPill status={row?.status} />;
}
