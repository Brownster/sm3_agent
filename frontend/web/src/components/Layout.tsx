import { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { MessageSquare, Activity, Github } from 'lucide-react';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path;

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link to="/" className="flex items-center gap-2 text-xl font-bold">
              <div className="w-8 h-8 bg-gradient-to-br from-orange-500 to-red-500 rounded-lg flex items-center justify-center">
                <span className="text-white text-sm font-bold">S</span>
              </div>
              <span>Sabio Monitoring Agent</span>
            </Link>

            <nav className="flex gap-1">
              <Link
                to="/chat"
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                  isActive('/chat')
                    ? 'bg-orange-500/20 text-orange-400'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`}
              >
                <MessageSquare className="w-4 h-4" />
                <span>Chat</span>
              </Link>

              <Link
                to="/monitoring"
                className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                  isActive('/monitoring')
                    ? 'bg-orange-500/20 text-orange-400'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`}
              >
                <Activity className="w-4 h-4" />
                <span>Monitoring</span>
              </Link>
            </nav>
          </div>

          <a
            href="https://github.com/grafana/mcp-grafana"
            target="_blank"
            rel="noopener noreferrer"
            className="text-gray-400 hover:text-white transition-colors"
          >
            <Github className="w-5 h-5" />
          </a>
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto px-4 py-6">
        {children}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 mt-12">
        <div className="container mx-auto px-4 py-6 text-center text-gray-500 text-sm">
          <p>Sabio Monitoring Agent v0.2.0 - Powered by SM3</p>
        </div>
      </footer>
    </div>
  );
}
