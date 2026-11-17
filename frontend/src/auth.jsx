import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "./api";
import Modal from "./components/Modal";

const AuthContext = createContext(null);

function LockGlyph({ className }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true" className={className}>
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" strokeLinecap="round" />
    </svg>
  );
}

export function LockIcon({ className }) {
  return <LockGlyph className={className} />;
}

function LoginDialog({ open, onClose }) {
  const { login } = useAuth();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) {
      setPassword("");
      setError("");
      setBusy(false);
    }
  }, [open]);

  const submit = async (event) => {
    event.preventDefault();
    if (!password.trim()) {
      setError("Enter the team password.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await login(password);
    } catch (err) {
      setError(err.status === 401 ? "Incorrect password." : err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Sign in to edit and download"
      subtitle="The full dashboard stays readable without an account, but edits and downloads need the team password."
    >
      <form onSubmit={submit} className="space-y-3">
        <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] text-slate-500 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
          <LockGlyph className="h-4 w-4 shrink-0 text-rr-600 dark:text-rr-300" />
          Public preview is limited to the first five rows of every table.
        </div>
        <div>
          <label htmlFor="login-password" className="label">
            Team password
          </label>
          <input
            id="login-password"
            type="password"
            autoComplete="current-password"
            className="input mt-1"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Enter password"
          />
        </div>
        {error ? (
          <p role="alert" className="text-xs font-semibold text-red-600 dark:text-red-400">
            {error}
          </p>
        ) : null}
        <div className="flex items-center justify-end gap-2 pt-1">
          <button type="button" className="btn-ghost" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export function AuthProvider({ children }) {
  const [authenticated, setAuthenticated] = useState(false);
  const [ready, setReady] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .authMe()
      .then((payload) => {
        if (!cancelled) setAuthenticated(Boolean(payload?.authenticated));
      })
      .catch(() => {
        if (!cancelled) setAuthenticated(false);
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });
    const onRequired = () => setDialogOpen(true);
    window.addEventListener("rr:auth-required", onRequired);
    return () => {
      cancelled = true;
      window.removeEventListener("rr:auth-required", onRequired);
    };
  }, []);

  const login = useCallback(async (password) => {
    await api.login(password);
    setAuthenticated(true);
    setDialogOpen(false);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setAuthenticated(false);
    }
  }, []);

  const openLogin = useCallback(() => setDialogOpen(true), []);
  const closeLogin = useCallback(() => setDialogOpen(false), []);

  const value = useMemo(
    () => ({ authenticated, ready, login, logout, openLogin, closeLogin, dialogOpen }),
    [authenticated, ready, login, logout, openLogin, closeLogin, dialogOpen],
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
      <LoginDialog open={dialogOpen} onClose={closeLogin} />
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
