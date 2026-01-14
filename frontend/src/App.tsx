import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './auth';
import ProtectedRoute from './components/ProtectedRoute';
import ErrorBoundary from './components/ErrorBoundary';
import { Toaster } from './components/Toast';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import History from './pages/History';
import Analytics from './pages/Analytics';
import Login from './pages/Login';
import AuthCallback from './pages/AuthCallback';
import { useWebSocket, useDarkMode } from './hooks';
import { ViewMode } from './types';

function AuthenticatedApp() {
  const [view, setView] = useState<ViewMode>('dashboard');
  const { state: wsState, queue, reconnect } = useWebSocket();
  const { isDark, toggleTheme } = useDarkMode();

  return (
    <Layout currentView={view} setView={setView} isDark={isDark} toggleTheme={toggleTheme}>
      {view === 'dashboard' && <Dashboard queue={queue} wsState={wsState} onReconnect={reconnect} />}
      {view === 'history' && <History />}
      {view === 'analytics' && <Analytics />}
    </Layout>
  );
}

const App = () => {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/auth/callback" element={<AuthCallback />} />

            {/* Protected routes */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <AuthenticatedApp />
                </ProtectedRoute>
              }
            />

            {/* Catch-all redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
      <Toaster />
    </ErrorBoundary>
  );
};

export default App;
