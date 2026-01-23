import { useState } from 'react';
import { Link, useLocation, Outlet } from 'react-router-dom';
import { clsx } from 'clsx';
import {
  FlaskConical,
  Upload,
  Briefcase,
  CheckSquare,
  Eye,
  Menu,
  X,
  LogOut,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import api from '../lib/api';

const navigation = [
  { name: 'Tool Testbench', href: '/', icon: FlaskConical },
  { name: 'Upload & Run', href: '/upload', icon: Upload },
  { name: 'Jobs Inspector', href: '/jobs', icon: Briefcase },
  { name: 'Approvals Inbox', href: '/approvals', icon: CheckSquare },
  { name: 'Evidence', href: '/observability', icon: Eye },
];

export default function Layout() {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const isAuthenticated = api.isAuthenticated();

  const handleLogout = () => {
    api.clearToken();
    window.location.reload();
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-gray-900/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-50 w-64 bg-gray-900 transform transition-transform duration-200 ease-in-out lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        <div className="flex h-16 items-center justify-between px-6 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-green-500 to-teal-600 rounded-lg flex items-center justify-center">
              <FlaskConical className="w-4 h-4 text-white" />
            </div>
            <span className="text-white font-semibold text-sm">Agent Testbench</span>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden text-gray-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="mt-6 px-3 space-y-1">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.name}
                to={item.href}
                onClick={() => setSidebarOpen(false)}
                className={clsx(
                  'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-gray-800 text-white'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                )}
              >
                <item.icon className="w-5 h-5" />
                {item.name}
              </Link>
            );
          })}
        </nav>

        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {isAuthenticated ? (
                <>
                  <CheckCircle2 className="w-4 h-4 text-green-500" />
                  <span className="text-xs text-green-500">Authenticated</span>
                </>
              ) : (
                <>
                  <XCircle className="w-4 h-4 text-red-500" />
                  <span className="text-xs text-red-500">Not Connected</span>
                </>
              )}
            </div>
            {isAuthenticated && (
              <button
                onClick={handleLogout}
                className="text-gray-400 hover:text-white p-1.5 rounded hover:bg-gray-800"
              >
                <LogOut className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 h-16 bg-white border-b border-gray-200 flex items-center px-4 lg:px-6">
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden p-2 -ml-2 rounded-lg text-gray-500 hover:bg-gray-100"
          >
            <Menu className="w-5 h-5" />
          </button>
          <h1 className="ml-2 lg:ml-0 text-lg font-semibold text-gray-900">
            {navigation.find((n) => n.href === location.pathname)?.name || 'Accounting Agent Tool Testbench'}
          </h1>
        </header>

        {/* Page content */}
        <main className="p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
