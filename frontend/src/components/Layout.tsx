import { Outlet, Link } from "react-router-dom";

export function Layout() {
  return (
    <div className="min-h-screen bg-surface-0 text-zinc-200 flex flex-col">
      <header className="border-b border-zinc-800 bg-surface-1">
        <div className="max-w-7xl mx-auto px-4 h-12 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
            <div className="w-6 h-6 rounded-full bg-blue-500/20 border border-blue-500/40 flex items-center justify-center">
              <div className="w-2 h-2 rounded-full bg-blue-400" />
            </div>
            <span className="font-semibold text-sm text-zinc-100">AgentLens</span>
            <span className="text-xs text-zinc-500">v0.1</span>
          </Link>
          <nav className="flex items-center gap-4 text-xs text-zinc-400">
            <Link to="/" className="hover:text-zinc-200 transition-colors">
              Traces
            </Link>
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  );
}
