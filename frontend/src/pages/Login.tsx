import { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { GitMerge, LogIn, AlertTriangle } from 'lucide-react';
import { SafeMotionDiv } from '../components/SafeMotion';
import { useAuth } from '../auth';
import type { AuthErrorType } from '../types';

// Error messages for user display
const ERROR_MESSAGES: Record<AuthErrorType, string> = {
  access_denied: 'You denied access to the application. Please try again.',
  invalid_state: 'Security validation failed. Please try logging in again.',
  network_error: 'Unable to connect to the server. Please check your connection.',
  token_expired: 'Your session has expired. Please log in again.',
  server_error: 'Server error occurred. Please try again later.',
  no_access: 'You do not have access to this project.',
};

export default function Login() {
  const { login, isAuthenticated, isLoading, error, clearError } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Redirect if already authenticated
  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, isLoading, navigate]);

  // Check for error from callback redirect
  const callbackError = searchParams.get('error');

  const handleLogin = () => {
    clearError();
    login();
  };

  const displayError =
    error ||
    (callbackError
      ? {
          type: callbackError as AuthErrorType,
          message: ERROR_MESSAGES[callbackError as AuthErrorType] || callbackError,
        }
      : null);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex items-center justify-center" role="status" aria-label="Loading">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" aria-hidden="true" />
        <span className="sr-only">Loading...</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex flex-col items-center justify-center p-4">
      {/* Background pattern */}
      <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 pointer-events-none mix-blend-overlay" />

      <SafeMotionDiv
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative z-10 w-full max-w-md"
      >
        {/* Logo & Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-orange-600 rounded-2xl mb-4 shadow-lg">
            <GitMerge className="w-8 h-8 text-white" aria-hidden="true" />
          </div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">MergeBot</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-2">
            GitLab Merge Queue Commander
          </p>
        </div>

        {/* Login Card */}
        <main className="bg-white dark:bg-slate-800/50 rounded-2xl border border-slate-200 dark:border-slate-700 p-8 shadow-xl backdrop-blur-sm">
          <h2 className="text-xl font-semibold text-slate-900 dark:text-white text-center mb-6">
            Sign in to continue
          </h2>

          {/* Error Alert */}
          {displayError && (
            <SafeMotionDiv
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              role="alert"
              aria-live="assertive"
              className="mb-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl flex items-start gap-3"
            >
              <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <p className="text-sm font-medium text-red-800 dark:text-red-300">
                  Authentication Failed
                </p>
                <p className="text-sm text-red-700 dark:text-red-400 mt-1">
                  {displayError.message}
                </p>
              </div>
            </SafeMotionDiv>
          )}

          {/* GitLab Login Button */}
          <button
            onClick={handleLogin}
            aria-label="Sign in with GitLab"
            className="w-full flex items-center justify-center gap-3 px-6 py-3 bg-orange-600 hover:bg-orange-700 text-white font-medium rounded-xl transition-colors shadow-lg shadow-orange-600/20 hover:shadow-orange-700/30 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
          >
            <LogIn className="w-5 h-5" aria-hidden="true" />
            Sign in with GitLab
          </button>

          <p className="text-center text-sm text-slate-500 dark:text-slate-400 mt-6">
            You'll be redirected to GitLab to authorize access
          </p>
        </main>

        {/* Footer */}
        <p className="text-center text-xs text-slate-400 dark:text-slate-500 mt-8">
          Only users with access to the configured GitLab project can sign in
        </p>
      </SafeMotionDiv>
    </div>
  );
}
