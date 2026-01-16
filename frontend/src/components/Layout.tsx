import React, { useState, useEffect } from 'react';
import { LayoutDashboard, History, BarChart2, GitMerge, Activity, Sun, Moon, ChevronLeft, ChevronRight, Menu, X, LogOut, User, AlertTriangle } from 'lucide-react';
import { ViewMode } from '../types';
import { useAuth } from '../auth';
import { config } from '../config';
import { useHealthCheck } from '../hooks/useHealthCheck';

interface LayoutProps {
  currentView: ViewMode;
  setView: (view: ViewMode) => void;
  children: React.ReactNode;
  isDark: boolean;
  toggleTheme: () => void;
}

const Layout: React.FC<LayoutProps> = ({ currentView, setView, children, isDark, toggleTheme }) => {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const { user, logout } = useAuth();
  const { isHealthy, mode, isLoading: isHealthLoading } = useHealthCheck();

  // Close mobile menu when view changes
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [currentView]);

  const navItems = [
    { id: 'dashboard', icon: LayoutDashboard, label: 'Live Queue' },
    { id: 'history', icon: History, label: 'History' },
    { id: 'analytics', icon: BarChart2, label: 'Analytics' },
  ] as const;

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-900 text-slate-900 dark:text-slate-100 overflow-hidden font-sans transition-colors duration-300">
      
      {/* Mobile Header */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-16 bg-white dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 z-30 flex items-center justify-between px-4 transition-colors duration-300">
        <div className="flex items-center space-x-2">
            <div className="bg-orange-600 p-1.5 rounded-lg shrink-0">
                <GitMerge className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-lg tracking-tight text-slate-900 dark:text-white">{config.appName}</span>
        </div>
        <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
            aria-label={isMobileMenuOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={isMobileMenuOpen}
            aria-controls="mobile-sidebar"
        >
            {isMobileMenuOpen ? <X className="w-6 h-6" aria-hidden="true" /> : <Menu className="w-6 h-6" aria-hidden="true" />}
        </button>
      </div>

      {/* Mobile Backdrop */}
      {isMobileMenuOpen && (
          <div 
            className="fixed inset-0 bg-slate-900/50 z-40 md:hidden backdrop-blur-sm transition-opacity"
            onClick={() => setIsMobileMenuOpen(false)}
          />
      )}

      {/* Sidebar */}
      <aside
        id="mobile-sidebar"
        role="navigation"
        aria-label="Main navigation"
        className={`
          fixed md:relative z-50 h-full
          ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
          ${isSidebarCollapsed ? 'md:w-20' : 'md:w-64'}
          w-64
          bg-white dark:bg-slate-950 border-r border-slate-200 dark:border-slate-800 flex flex-col shadow-xl transition-all duration-300 ease-in-out
        `}
      >
        {/* Desktop Collapse Toggle Button */}
        <button
          onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          className="hidden md:block absolute -right-3 top-8 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-full p-1 text-slate-500 hover:text-slate-700 dark:hover:text-slate-200 shadow-sm z-50 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
          aria-label={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!isSidebarCollapsed}
        >
          {isSidebarCollapsed ? <ChevronRight className="w-4 h-4" aria-hidden="true" /> : <ChevronLeft className="w-4 h-4" aria-hidden="true" />}
        </button>

        {/* Sidebar Header (Visible on Desktop) */}
        <div className={`hidden md:flex p-6 items-center ${isSidebarCollapsed ? 'justify-center' : 'space-x-3'} border-b border-slate-200 dark:border-slate-800`}>
          <div className="bg-orange-600 p-2 rounded-lg shrink-0">
            <GitMerge className="w-6 h-6 text-white" />
          </div>
          {!isSidebarCollapsed && (
            <div className="overflow-hidden whitespace-nowrap">
              <h1 className="font-bold text-lg tracking-tight text-slate-900 dark:text-white">{config.appName}</h1>
              <p className="text-xs text-slate-500 font-mono">v{config.appVersion} • {isHealthLoading ? '...' : isHealthy ? 'Active' : 'Offline'}</p>
            </div>
          )}
        </div>

        {/* Mobile Sidebar Header (Brand only, close button is in top bar but redundant check here is fine) */}
        <div className="md:hidden p-6 flex items-center space-x-3 border-b border-slate-200 dark:border-slate-800">
           <div className="bg-orange-600 p-2 rounded-lg shrink-0">
            <GitMerge className="w-6 h-6 text-white" />
          </div>
          <div className="overflow-hidden whitespace-nowrap">
              <h1 className="font-bold text-lg tracking-tight text-slate-900 dark:text-white">{config.appName}</h1>
              <p className="text-xs text-slate-500 font-mono">v{config.appVersion} • {isHealthLoading ? '...' : isHealthy ? 'Active' : 'Offline'}</p>
            </div>
        </div>

        <nav className="flex-1 p-4 space-y-2 overflow-y-auto" aria-label="Main menu">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setView(item.id)}
              className={`flex items-center ${isSidebarCollapsed ? 'justify-center md:px-0' : 'space-x-3'} w-full p-3 rounded-lg transition-all duration-200 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none ${
                currentView === item.id
                  ? 'bg-blue-600/10 text-blue-600 dark:text-blue-400 border border-blue-600/20 shadow-[0_0_15px_rgba(37,99,235,0.1)]'
                  : 'text-slate-500 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-900 hover:text-slate-900 dark:hover:text-slate-200'
              }`}
              aria-label={`Go to ${item.label}`}
              aria-current={currentView === item.id ? 'page' : undefined}
              title={isSidebarCollapsed ? item.label : undefined}
            >
              <item.icon className="w-5 h-5 shrink-0" aria-hidden="true" />
              {(!isSidebarCollapsed || isMobileMenuOpen) && <span className="font-medium md:block">{item.label}</span>}
            </button>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-200 dark:border-slate-800 space-y-4">
           {/* Theme Toggle */}
           <button
             onClick={toggleTheme}
             className={`w-full flex items-center ${isSidebarCollapsed ? 'justify-center md:px-0' : 'space-x-3'} p-3 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-900 transition-colors text-slate-500 dark:text-slate-400 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none`}
             aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
             title={isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
           >
              {isDark ? <Sun className="w-5 h-5" aria-hidden="true" /> : <Moon className="w-5 h-5" aria-hidden="true" />}
              {(!isSidebarCollapsed || isMobileMenuOpen) && <span>{isDark ? 'Light Mode' : 'Dark Mode'}</span>}
           </button>

           {/* User Profile & Logout */}
           {user && (
             <div className={`flex items-center ${isSidebarCollapsed ? 'justify-center md:px-0' : 'justify-between'} p-3 rounded-lg bg-slate-100 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800`}>
               <div className={`flex items-center ${isSidebarCollapsed ? '' : 'space-x-3'}`}>
                 {user.avatar_url ? (
                   <img
                     src={user.avatar_url}
                     alt={user.name}
                     className="w-8 h-8 rounded-full border border-slate-200 dark:border-slate-700 shrink-0"
                   />
                 ) : (
                   <User className="w-5 h-5 text-slate-500 shrink-0" />
                 )}
                 {(!isSidebarCollapsed || isMobileMenuOpen) && (
                   <div className="text-xs overflow-hidden">
                     <p className="text-slate-700 dark:text-slate-200 font-medium truncate">
                       {user.name}
                     </p>
                     <p className="text-slate-500 truncate">@{user.username}</p>
                   </div>
                 )}
               </div>
               {(!isSidebarCollapsed || isMobileMenuOpen) && (
                 <button
                   onClick={logout}
                   className="p-2 text-slate-400 hover:text-red-500 transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none rounded"
                   aria-label="Sign out"
                   title="Sign out"
                 >
                   <LogOut className="w-4 h-4" aria-hidden="true" />
                 </button>
               )}
             </div>
           )}

           {/* System Health */}
           <div className={`flex items-center ${isSidebarCollapsed ? 'justify-center md:px-0' : 'space-x-3'} p-3 rounded-lg bg-slate-100 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800`}>
              {isHealthLoading ? (
                <Activity className="w-4 h-4 text-slate-400 animate-pulse shrink-0" />
              ) : isHealthy ? (
                <Activity className="w-4 h-4 text-green-500 animate-pulse shrink-0" />
              ) : mode === 'degraded' ? (
                <AlertTriangle className="w-4 h-4 text-yellow-500 shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-red-500 shrink-0" />
              )}
              {(!isSidebarCollapsed || isMobileMenuOpen) && (
                <div className="text-xs overflow-hidden">
                   <p className="text-slate-600 dark:text-slate-300 font-medium">
                     {isHealthLoading ? 'Checking...' : isHealthy ? 'System Healthy' : mode === 'degraded' ? 'Degraded' : 'Disconnected'}
                   </p>
                   <p className="text-slate-500">
                     {isHealthLoading ? 'Connecting...' : isHealthy ? 'Backend Connected' : mode === 'degraded' ? 'Partial Connectivity' : 'Backend Unreachable'}
                   </p>
                </div>
              )}
           </div>
        </div>
      </aside>

      {/* Main Content */}
      <main id="main-content" className="flex-1 overflow-y-auto bg-slate-50 dark:bg-slate-900 relative transition-colors duration-300 pt-16 md:pt-0" tabIndex={-1}>
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 pointer-events-none mix-blend-overlay"></div>
        <div className="max-w-7xl mx-auto p-4 md:p-8 relative z-10">
          {children}
        </div>
      </main>
    </div>
  );
};

export default Layout;