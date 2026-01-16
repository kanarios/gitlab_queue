import React from 'react';
import { XCircle, RefreshCw, AlertTriangle } from 'lucide-react';

type ErrorVariant = 'inline' | 'full';

interface ErrorDisplayProps {
  error: string | Error;
  onRetry?: () => void;
  title?: string;
  variant?: ErrorVariant;
  className?: string;
}

/**
 * Reusable error display component with optional retry button.
 *
 * @param error - Error message or Error object
 * @param onRetry - Optional callback for retry button
 * @param title - Optional custom title (defaults based on variant)
 * @param variant - 'inline' for section errors, 'full' for full-page errors
 * @param className - Additional CSS classes
 */
const ErrorDisplay: React.FC<ErrorDisplayProps> = ({
  error,
  onRetry,
  title,
  variant = 'inline',
  className = '',
}) => {
  const errorMessage = error instanceof Error ? error.message : error;

  if (variant === 'full') {
    return (
      <div className={`p-12 text-center ${className}`}>
        <XCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
        <h3 className="text-lg font-medium text-slate-900 dark:text-white mb-2">
          {title || 'Something went wrong'}
        </h3>
        <p className="text-red-600 dark:text-red-400 mb-4">
          {errorMessage}
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        )}
      </div>
    );
  }

  // Inline variant (for sections/cards)
  return (
    <div
      className={`bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-700/50 rounded-xl p-4 ${className}`}
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          {title && (
            <h4 className="text-sm font-medium text-red-800 dark:text-red-300 mb-1">
              {title}
            </h4>
          )}
          <p className="text-sm text-red-700 dark:text-red-400 break-words">
            {errorMessage}
          </p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-lg hover:bg-red-200 dark:hover:bg-red-900/50 transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Retry
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default ErrorDisplay;
