import { Link, Route, Routes } from "react-router-dom";
import Submit from "./screens/Submit";
import Progress from "./screens/Progress";
import Report from "./screens/Report";
import History from "./screens/History";

export default function App() {
  return (
    <div className="min-h-full">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-5xl px-6 py-4 flex items-center justify-between">
          <Link to="/" className="font-semibold text-lg tracking-tight">
            Preflight <span className="text-sky-600">AI</span>
          </Link>
          <nav className="text-sm text-slate-600 flex gap-6">
            <Link to="/" className="hover:text-slate-900">New run</Link>
            <Link to="/history" className="hover:text-slate-900">History</Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-8">
        <Routes>
          <Route path="/" element={<Submit />} />
          <Route path="/runs/:runId/progress" element={<Progress />} />
          <Route path="/runs/:runId/report" element={<Report />} />
          <Route path="/history" element={<History />} />
        </Routes>
      </main>
    </div>
  );
}
