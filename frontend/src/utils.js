export function cx(...parts) {
  return parts.filter(Boolean).join(" ");
}

export function normaliseName(value) {
  return String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

export function compactName(value) {
  return normaliseName(value).replace(/\s+/g, "");
}

export function isNumber(value) {
  return typeof value === "number" && Number.isFinite(value);
}

export function fmtNum(value, digits = 1) {
  if (!isNumber(value)) return "—";
  return value.toLocaleString("en-IN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function fmtInt(value) {
  if (!isNumber(value)) return "—";
  return Math.round(value).toLocaleString("en-IN");
}

export function fmtSigned(value, digits = 1) {
  if (!isNumber(value)) return "—";
  const text = fmtNum(Math.abs(value), digits);
  return value > 0 ? `+${text}` : value < 0 ? `−${text}` : text;
}

export function fmtPct(value, digits = 1) {
  if (!isNumber(value)) return "—";
  return `${fmtNum(value, digits)}%`;
}

export function fmtDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function fmtDateTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function initials(name) {
  return String(name ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export const STATUS_ORDER = ["retained", "rr_own", "pool", "unknown", "no_ipl"];

export const STATUS_META = {
  retained: {
    label: "Retained",
    short: "Retained",
    pill: "bg-sky-100 text-sky-800 ring-sky-600/20 dark:bg-sky-500/15 dark:text-sky-300 dark:ring-sky-400/30",
    dot: "bg-sky-500",
    description: "Already retained or in the existing squad — excluded from the available pool.",
  },
  rr_own: {
    label: "RR own",
    short: "RR own",
    pill: "bg-rr-100 text-rr-800 ring-rr-600/20 dark:bg-rr-500/15 dark:text-rr-300 dark:ring-rr-400/30",
    dot: "bg-rr-500",
    description: "RR-contracted player — excluded from the available pool.",
  },
  pool: {
    label: "In pool",
    short: "Pool",
    pill: "bg-emerald-100 text-emerald-800 ring-emerald-600/20 dark:bg-emerald-500/15 dark:text-emerald-300 dark:ring-emerald-400/30",
    dot: "bg-emerald-500",
    description: "Available for the auction pool; included in clean rankings.",
  },
  unknown: {
    label: "Unknown",
    short: "Unknown",
    pill: "bg-amber-100 text-amber-900 ring-amber-600/20 dark:bg-amber-500/15 dark:text-amber-300 dark:ring-amber-400/30",
    dot: "bg-amber-500",
    description: "Availability unverified — treated as available until confirmed.",
  },
  no_ipl: {
    label: "No IPL",
    short: "No IPL",
    pill: "bg-slate-200 text-slate-700 ring-slate-500/20 dark:bg-slate-700/40 dark:text-slate-300 dark:ring-slate-500/30",
    dot: "bg-slate-400",
    description: "Has not played the IPL — excluded from the available pool.",
  },
};

export function statusMeta(status) {
  return STATUS_META[status] ?? STATUS_META.unknown;
}

export function flagBadges(row) {
  const badges = [];
  if (String(row?.qualification_status ?? "").toUpperCase() === "BELOW_MIN") {
    badges.push({
      key: "below-min",
      label: "BELOW_MIN",
      tone: "amber",
      title: "This player does not meet the analysis package's role-specific qualification criteria.",
    });
  }
  if (String(row?.SAMPLE_FLAG ?? "").toUpperCase() === "WIDE") {
    badges.push({
      key: "sample",
      label: "WIDE RANK",
      tone: "amber",
      title: "Wide 90% rank interval — sample-limited. Do not over-read the exact rank.",
    });
  }
  if (String(row?.RECENT_FORM_FLAG ?? "").toUpperCase() === "LOW") {
    badges.push({
      key: "recent",
      label: "LOW 2026",
      tone: "sky",
      title: "RECENT_FORM_FLAG is LOW — 2026 form sample is thin or weak.",
    });
  }
  if (String(row?.IPL_PRESSURE_FLAG ?? "").toUpperCase() === "LOW") {
    badges.push({
      key: "ipl-pressure",
      label: "LOW IPL P",
      tone: "slate",
      title: "IPL_PRESSURE_FLAG is LOW — limited IPL pressure sample.",
    });
  }
  if (String(row?.PLAYED_2026_IPL ?? "").toUpperCase() === "N") {
    badges.push({
      key: "no-2026",
      label: "NO 2026",
      tone: "slate",
      title: "Did not play the 2026 IPL in the supplied data.",
    });
  }
  return badges;
}

export const BADGE_TONES = {
  amber:
    "bg-amber-100 text-amber-900 ring-amber-600/20 dark:bg-amber-500/15 dark:text-amber-300 dark:ring-amber-400/30",
  sky:
    "bg-sky-100 text-sky-800 ring-sky-600/20 dark:bg-sky-500/15 dark:text-sky-300 dark:ring-sky-400/30",
  slate:
    "bg-slate-200 text-slate-700 ring-slate-500/20 dark:bg-slate-700/40 dark:text-slate-300 dark:ring-slate-500/30",
  emerald:
    "bg-emerald-100 text-emerald-800 ring-emerald-600/20 dark:bg-emerald-500/15 dark:text-emerald-300 dark:ring-emerald-400/30",
};

export function downloadCsv(filename, columns, rows) {
  const escape = (value) => {
    if (value === null || value === undefined) return "";
    const text = String(value);
    if (/[",\n\r]/.test(text)) {
      return `"${text.replace(/"/g, '""')}"`;
    }
    return text;
  };
  const header = columns.map((column) => escape(column.header)).join(",");
  const body = rows
    .map((row) => columns.map((column) => escape(column.value(row))).join(","))
    .join("\r\n");
  const blob = new Blob([`\uFEFF${header}\r\n${body}`], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function compareValues(a, b) {
  const aMissing = a === null || a === undefined || a === "";
  const bMissing = b === null || b === undefined || b === "";
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1;
  if (bMissing) return -1;
  if (typeof a === "number" && typeof b === "number") return a - b;
  return String(a).localeCompare(String(b), "en", { sensitivity: "base" });
}

export function rangePercent(value, domainMin, domainMax) {
  if (!isNumber(value) || domainMax <= domainMin) return 0;
  return Math.min(100, Math.max(0, ((value - domainMin) / (domainMax - domainMin)) * 100));
}
