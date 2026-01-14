import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { GitMerge, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { SafeMotionDiv } from '../components/SafeMotion';
import { handleCallback } from '../auth/api';
import { useAuth } from '../auth';
import type { AuthError } from '../types';

type CallbackState = 'processing' | 'success' | 'error';

export default function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { setUser } = useAuth();

  const [state, setState] = useState<CallbackState>('processing');
  const [error, setError] = useState<AuthError | null>(null);

  useEffect(() => {
    async function processCallback() {
      const code = searchParams.get('code');
      const oauthState = searchParams.get('state');
      const errorParam = searchParams.get('error');
      const errorDescription = searchParams.get('error_description');

      // Handle OAuth error response from GitLab
      if (errorParam) {
        setState('error');
        setError({
          type: errorParam === 'access_denied' ? 'access_denied' : 'server_error',
          message: errorDescription || 'Authorization was denied',
        });
        return;
      }

      // Validate required parameters
      if (!code || !oauthState) {
        setState('error');
        setError({
          type: 'invalid_state',
          message: 'Missing required OAuth parameters',
        });
        return;
      }

      // Exchange code for token
      const result = await handleCallback(code, oauthState);

      if (result.success) {
        setUser(result.user);
        setState('success');
        // Redirect to dashboard after brief success display
        setTimeout(() => {
          navigate('/', { replace: true });
        }, 1500);
      } else {
        setState('error');
        setError(result.error);
      }
    }

    processCallback();
  }, [searchParams, navigate, setUser]);

  const handleRetry = () => {
    // Redirect to login with error type for display
    navigate(`/login${error ? `?error=${error.type}` : ''}`, { replace: true });
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex flex-col items-center justify-center p-4">
      <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20 pointer-events-none mix-blend-overlay" />

      <SafeMotionDiv
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="relative z-10 text-center"
      >
        {/* Logo */}
        <div className="inline-flex items-center justify-center w-16 h-16 bg-orange-600 rounded-2xl mb-6 shadow-lg">
          <GitMerge className="w-8 h-8 text-white" aria-hidden="true" />
        </div>

        {/* Processing State */}
        {state === 'processing' && (
          <div className="space-y-4" role="status" aria-live="polite">
            <Loader2 className="w-12 h-12 text-blue-600 animate-spin mx-auto" aria-hidden="true" />
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
              Signing you in...
            </h2>
            <p className="text-slate-500 dark:text-slate-400">
              Please wait while we complete authentication
            </p>
          </div>
        )}

        {/* Success State */}
        {state === 'success' && (
          <SafeMotionDiv
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            className="space-y-4"
            role="status"
            aria-live="polite"
          >
            <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto" aria-hidden="true" />
            <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Welcome!</h2>
            <p className="text-slate-500 dark:text-slate-400">Redirecting to dashboard...</p>
          </SafeMotionDiv>
        )}

        {/* Error State */}
        {state === 'error' && (
          <SafeMotionDiv
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            className="space-y-6"
            role="alert"
            aria-live="assertive"
          >
            <XCircle className="w-16 h-16 text-red-500 mx-auto" aria-hidden="true" />
            <div>
              <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                Authentication Failed
              </h2>
              <p className="text-slate-500 dark:text-slate-400 mt-2 max-w-sm">
                {error?.message || 'An unexpected error occurred'}
              </p>
            </div>
            <button
              onClick={handleRetry}
              aria-label="Try signing in again"
              className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-xl transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
            >
              Try Again
            </button>
          </SafeMotionDiv>
        )}
      </SafeMotionDiv>
    </div>
  );
}
