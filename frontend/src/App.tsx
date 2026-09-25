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
import { ProjectProvider, useProject } from './projects/ProjectContext';

function ProjectWorkspace({ projectId, view }: { projectId: number; view: ViewMode }) {
  const { state: wsState, queue, reconnect } = useWebSocket(projectId);

  if (view === 'dashboard') {
    return <Dashboard queue={queue} wsState={wsState} onReconnect={reconnect} />;
  }
  if (view === 'history') return <History projectId={projectId} />;
  return <Analytics projectId={projectId} />;
}

function AuthenticatedWorkspace() {
  const [view, setView] = useState<ViewMode>('dashboard');
  const { isDark, toggleTheme } = useDarkMode();
  const { selectedProject, isLoading, error, retry } = useProject();

  return (
    <Layout currentView={view} setView={setView} isDark={isDark} toggleTheme={toggleTheme}>
      {isLoading ? (
        <div className="py-16 text-center text-sm text-slate-500 dark:text-slate-400" role="status" aria-live="polite">
          Loading your GitLab projects…
        </div>
      ) : selectedProject ? (
        <ProjectWorkspace key={selectedProject.project_id} projectId={selectedProject.project_id} view={view} />
      ) : error ? (
        <section className="mx-auto mt-8 max-w-lg rounded-xl border border-red-200 bg-white p-6 text-center dark:border-red-900/60 dark:bg-slate-800" role="alert">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Projects could not be loaded</h2>
          <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{error}</p>
          <button
            type="button"
            onClick={retry}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
          >
            Try again
          </button>
        </section>
      ) : (
        <div className="py-16 text-center" role="status">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white">No GitLab projects available</h2>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">Ask a GitLab administrator to grant this account access to a project.</p>
        </div>
      )}
    </Layout>
  );
}

function AuthenticatedApp() {
  return (
    <ProjectProvider>
      <AuthenticatedWorkspace />
    </ProjectProvider>
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
