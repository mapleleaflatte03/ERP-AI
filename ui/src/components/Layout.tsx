import { useState, useCallback, useEffect } from 'react';
import { Link, useLocation, Outlet } from 'react-router-dom';
import { clsx } from 'clsx';
import {
  FileText,
  Edit3,
  CheckSquare,
  ArrowLeftRight,
  MessageCircle,
  BarChart3,
  Clock,
  Menu,
  X,
  LogOut,
  CheckCircle2,

  Settings,
  Bot,
} from 'lucide-react';
import api from '../lib/api';
import LoginModal from './LoginModal';
import { CommandPalette } from './CommandPalette';

const navigation = [
  { name: 'Chứng từ', href: '/', icon: FileText },
  { name: 'Đề xuất hạch toán', href: '/proposals', icon: Edit3 },
  { name: 'Duyệt', href: '/approvals', icon: CheckSquare },
  { name: 'Đối chiếu', href: '/reconciliation', icon: ArrowLeftRight, comingSoon: true },
  { name: 'Trợ lý AI', href: '/copilot', icon: MessageCircle, beta: true },
  { name: 'Báo cáo', href: '/analyze', icon: BarChart3 },
  { name: 'Lịch sử', href: '/evidence', icon: Clock },
];

const adminNavigation = [
  { name: 'Diagnostics', href: '/admin/diagnostics', icon: Settings },
];

export default function Layout() {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  const [showPrefs, setShowPrefs] = useState(false);
  // Use state to track auth and trigger re-render after login
  const [isAuthenticated, setIsAuthenticated] = useState(() => api.isAuthenticated());
  const [uiPrefs, setUiPrefs] = useState(() => {
    try {
      const raw = localStorage.getItem('erpx_ui_prefs');
      if (!raw) {
        return { theme: 'light', density: 'comfortable', motion: 'normal' };
      }
      const parsed = JSON.parse(raw);
      return {
        theme: parsed.theme || 'light',
        density: parsed.density || 'comfortable',
        motion: parsed.motion || 'normal',
      };
    } catch {
      return { theme: 'light', density: 'comfortable', motion: 'normal' };
    }
  });

  const handleLoginSuccess = useCallback(() => {
    setIsAuthenticated(true);
  }, []);

  const handleLogout = () => {
    api.clearToken();
    setIsAuthenticated(false);
  };

  useEffect(() => {
    try {
      localStorage.setItem('erpx_ui_prefs', JSON.stringify(uiPrefs));
    } catch {
      // ignore
    }
    const root = document.documentElement;
    root.setAttribute('data-theme', uiPrefs.theme);
    root.setAttribute('data-density', uiPrefs.density);
    root.setAttribute('data-motion', uiPrefs.motion);
  }, [uiPrefs]);

  // Show login modal if not authenticated
  if (!isAuthenticated) {
    return <LoginModal onSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <CommandPalette />
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
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-cyan-600 rounded-lg flex items-center justify-center">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <span className="text-white font-semibold text-sm">AI Kế Toán</span>
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
            const isActive = location.pathname === item.href ||
              (item.href === '/' && location.pathname.startsWith('/documents'));

            // Handle Coming Soon items
            if ((item as any).comingSoon) {
              return (
                <div key={item.name} className="flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium text-gray-500 cursor-not-allowed opacity-60">
                  <div className="flex items-center gap-3">
                    <item.icon className="w-5 h-5" />
                    {item.name}
                  </div>
                  <span className="text-[10px] bg-gray-800 text-gray-400 px-1.5 py-0.5 rounded border border-gray-700">SOON</span>
                </div>
              );
            }

            return (
              <Link
                key={item.name}
                to={item.href}
                onClick={() => setSidebarOpen(false)}
                className={clsx(
                  'flex items-center justify-between px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-gray-800 text-white'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                )}
              >
                <div className="flex items-center gap-3">
                  <item.icon className="w-5 h-5" />
                  {item.name}
                </div>
                {(item as any).beta && (
                  <span className="text-[10px] bg-indigo-500/20 text-indigo-300 px-1.5 py-0.5 rounded border border-indigo-500/30">BETA</span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Admin toggle */}
        {showAdmin && (
          <nav className="mt-4 px-3 pt-4 border-t border-gray-800 space-y-1">
            <div className="px-3 py-1 text-xs text-gray-500 uppercase tracking-wider">Admin</div>
            {adminNavigation.map((item) => {
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
        )}

        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-500" />
              <span className="text-xs text-green-500">Đã kết nối</span>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setShowAdmin(!showAdmin)}
                className={clsx(
                  'p-1.5 rounded hover:bg-gray-800',
                  showAdmin ? 'text-white' : 'text-gray-500'
                )}
                title="Toggle Admin Menu"
              >
                <Settings className="w-4 h-4" />
              </button>
              <button
                onClick={handleLogout}
                className="text-gray-400 hover:text-white p-1.5 rounded hover:bg-gray-800"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
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
          <div className="flex-1 flex items-center justify-between">
            <h1 className="ml-2 lg:ml-0 text-lg font-semibold text-gray-900">
              {navigation.find((n) => n.href === location.pathname)?.name ||
                adminNavigation.find((n) => n.href === location.pathname)?.name ||
                'AI Kế Toán'}
            </h1>
            <div className="flex items-center gap-3">
              <div className="hidden md:flex items-center gap-2 text-xs text-gray-400">
                <span className="px-2 py-1 bg-gray-100 rounded border">⌘K</span>
                <span>to search</span>
              </div>
              <div className="relative">
                <button
                  onClick={() => setShowPrefs((prev) => !prev)}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
                >
                  <Settings className="w-4 h-4" />
                  <span className="text-xs">Appearance</span>
                </button>
                {showPrefs && (
                  <div className="absolute right-0 mt-2 w-64 rounded-xl border bg-white shadow-lg p-3 text-xs text-gray-700 z-50">
                    <div className="font-semibold text-gray-900 mb-2">UI Preferences</div>
                    <div className="space-y-2">
                      <div>
                        <div className="text-[11px] text-gray-500 mb-1">Theme</div>
                        <div className="flex gap-2">
                          {['light', 'dark'].map((theme) => (
                            <button
                              key={theme}
                              onClick={() => setUiPrefs((prev) => ({ ...prev, theme }))}
                              className={`px-2 py-1 rounded border ${
                                uiPrefs.theme === theme
                                  ? 'bg-gray-900 text-white border-gray-900'
                                  : 'bg-white text-gray-600 border-gray-200'
                              }`}
                            >
                              {theme}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div>
                        <div className="text-[11px] text-gray-500 mb-1">Density</div>
                        <div className="flex gap-2">
                          {['compact', 'comfortable', 'spacious'].map((density) => (
                            <button
                              key={density}
                              onClick={() => setUiPrefs((prev) => ({ ...prev, density }))}
                              className={`px-2 py-1 rounded border ${
                                uiPrefs.density === density
                                  ? 'bg-gray-900 text-white border-gray-900'
                                  : 'bg-white text-gray-600 border-gray-200'
                              }`}
                            >
                              {density}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div>
                        <div className="text-[11px] text-gray-500 mb-1">Motion</div>
                        <div className="flex gap-2">
                          {['normal', 'reduced'].map((motion) => (
                            <button
                              key={motion}
                              onClick={() => setUiPrefs((prev) => ({ ...prev, motion }))}
                              className={`px-2 py-1 rounded border ${
                                uiPrefs.motion === motion
                                  ? 'bg-gray-900 text-white border-gray-900'
                                  : 'bg-white text-gray-600 border-gray-200'
                              }`}
                            >
                              {motion}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
