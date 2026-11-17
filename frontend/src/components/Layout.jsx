import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth, LockIcon } from "../auth";
import { useTheme } from "../theme";
import { cx } from "../utils";

function BrandMark() {
  return (
    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-rr-500 to-rr-700 text-sm font-black tracking-tight text-white shadow-sm">
      RR
    </span>
  );
}

const NAV_LINKS = [
  { to: "/", label: "Start here", end: true },
  { to: "/overview", label: "Overview" },
  { to: "/batters", label: "Batters" },
  { to: "/bowlers", label: "Bowlers" },
  { to: "/stats-explorer", label: "Stats Explorer" },
  { to: "/players", label: "All Players" },
  { to: "/teams", label: "Teams" },
  { to: "/availability", label: "Availability" },
  { to: "/rr-fit", label: "RR Fit" },
  { to: "/auction-board", label: "Auction Board" },
  { to: "/methods", label: "Data & Methods" },
];

function SunIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true" {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" strokeLinecap="round" />
    </svg>
  );
}

function MoonIcon(props) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true" {...props}>
      <path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11Z" strokeLinejoin="round" />
    </svg>
  );
}

function ThemeToggle() {
  const { theme, toggle } = useTheme();
  const dark = theme === "dark";
  return (
    <button
      type="button"
      onClick={toggle}
      className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-600 transition-colors hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Light mode" : "Dark mode"}
    >
      {dark ? <SunIcon className="h-[18px] w-[18px]" /> : <MoonIcon className="h-[18px] w-[18px]" />}
    </button>
  );
}

function AuthButton() {
  const { authenticated, ready, logout, openLogin } = useAuth();
  if (!ready) {
    return <span className="h-9 w-20 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />;
  }
  if (authenticated) {
    return (
      <button
        type="button"
        onClick={logout}
        className="flex h-9 items-center gap-1.5 rounded-lg border border-emerald-300 bg-emerald-50 px-2.5 text-xs font-semibold text-emerald-800 transition-colors hover:bg-emerald-100 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300"
        title="Signed in — click to sign out"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
        <span className="hidden sm:inline">Scout</span>
        <span className="text-[10px] font-medium opacity-70">Sign out</span>
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={openLogin}
      className="flex h-9 items-center gap-1.5 rounded-lg bg-rr-600 px-3 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-rr-700"
      title="Sign in to edit and download"
    >
      <LockIcon className="h-3.5 w-3.5" />
      Log in
    </button>
  );
}

function NavItems({ mobile = false, onNavigate }) {
  return NAV_LINKS.map((link) => (
    <NavLink
      key={link.to}
      to={link.to}
      end={link.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        cx(
          "rounded-lg text-sm font-medium transition-colors",
          mobile ? "block px-3 py-2" : "px-3 py-1.5",
          isActive
            ? "bg-rr-50 text-rr-700 dark:bg-rr-500/10 dark:text-rr-300"
            : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white",
        )
      }
    >
      {link.label}
    </NavLink>
  ));
}

export default function Layout() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="no-print sticky top-0 z-40 border-b border-slate-200/80 bg-white/85 backdrop-blur dark:border-slate-800/80 dark:bg-slate-950/85">
        <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6">
          <Link to="/" className="flex min-w-0 items-center gap-3">
            <BrandMark />
            <span className="min-w-0">
              <span className="block truncate text-sm font-bold leading-tight tracking-tight text-slate-900 dark:text-white">
                Reliability Under Pressure
              </span>
              <span className="hidden truncate text-[11px] font-medium text-slate-500 dark:text-slate-400 sm:block">
                RR · IPL 2027 auction scouting
              </span>
            </span>
          </Link>

          <nav className="ml-6 hidden items-center gap-1 lg:flex" aria-label="Primary">
            <NavItems />
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <AuthButton />
            <ThemeToggle />
            <button
              type="button"
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-300 bg-white text-slate-600 lg:hidden dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
              onClick={() => setOpen((value) => !value)}
              aria-expanded={open}
              aria-label="Toggle navigation menu"
            >
              {open ? (
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M6 6l12 12M18 6L6 18" strokeLinecap="round" />
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {open && (
          <nav className="border-t border-slate-200 bg-white px-4 py-2 lg:hidden dark:border-slate-800 dark:bg-slate-950" aria-label="Mobile">
            <NavItems mobile onNavigate={() => setOpen(false)} />
          </nav>
        )}
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
        <Outlet />
      </main>

      <footer className="no-print border-t border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-950">
        <div className="mx-auto max-w-7xl space-y-3 px-4 py-8 text-xs leading-relaxed text-slate-500 sm:px-6 dark:text-slate-400">
          <p className="font-semibold text-slate-700 dark:text-slate-300">
            Reliability Under Pressure — decision support, not a prediction.
          </p>
          <p>
            Player scores and ranks are imported from the supplied RR 2027 master analysis CSV.
            Its scope is IPL 2022–2026 plus the T20I competitions in the pack; the source does
            not verify 2027 registration, contracts, injuries or auction availability. Treat
            bowling ranks as descriptive rather than a stable skill hierarchy.
          </p>
          <p>
            Availability status is an unverified scouting judgement from public news until official
            IPL announcements. Edit it in the Availability workspace. The confidential raw
            competition pack is never copied into this frontend or any API response.
          </p>
        </div>
      </footer>
    </div>
  );
}
