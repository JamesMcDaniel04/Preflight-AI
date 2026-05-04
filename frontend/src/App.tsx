import { useState } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import { RequireAuth, useAuth } from "./auth";
import SettingsPanel from "./components/SettingsPanel";
import History from "./screens/History";
import Login from "./screens/Login";
import Progress from "./screens/Progress";
import Report from "./screens/Report";
import Signup from "./screens/Signup";
import Submit from "./screens/Submit";

export default function App() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const { user, ready, logout } = useAuth();

  return (
    <div className="min-h-full">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <Link to={user ? "/" : "/login"} className="text-lg font-semibold tracking-tight">
            Preflight <span className="text-sky-600">AI</span>
          </Link>
          {user && (
            <nav className="flex items-center gap-6 text-sm text-slate-600">
              <Link to="/" className="hover:text-slate-900">
                New run
              </Link>
              <Link to="/history" className="hover:text-slate-900">
                History
              </Link>
              <button
                type="button"
                onClick={() => setSettingsOpen(true)}
                className="hover:text-slate-900"
              >
                Settings
              </button>
              <span className="text-slate-400">{user.email}</span>
              <button type="button" onClick={() => logout()} className="hover:text-slate-900">
                Logout
              </button>
            </nav>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">
        {!ready ? (
          <div className="text-sm text-slate-500">Loading session...</div>
        ) : (
          <Routes>
            <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
            <Route path="/signup" element={user ? <Navigate to="/" replace /> : <Signup />} />
            <Route
              path="/"
              element={
                <RequireAuth>
                  <Submit onOpenSettings={() => setSettingsOpen(true)} />
                </RequireAuth>
              }
            />
            <Route
              path="/runs/:runId/progress"
              element={
                <RequireAuth>
                  <Progress />
                </RequireAuth>
              }
            />
            <Route
              path="/runs/:runId/report"
              element={
                <RequireAuth>
                  <Report />
                </RequireAuth>
              }
            />
            <Route
              path="/history"
              element={
                <RequireAuth>
                  <History />
                </RequireAuth>
              }
            />
          </Routes>
        )}
      </main>
      <SettingsPanel open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
