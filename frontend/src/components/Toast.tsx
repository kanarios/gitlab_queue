import { Toaster as SonnerToaster, toast } from 'sonner';

/**
 * Pre-configured Toaster component with dark mode support.
 * Add this component once in App.tsx.
 */
export const Toaster = () => (
  <SonnerToaster
    position="top-right"
    toastOptions={{
      duration: 4000,
      classNames: {
        toast:
          'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white shadow-lg',
        title: 'text-slate-900 dark:text-white font-medium',
        description: 'text-slate-500 dark:text-slate-400 text-sm',
        actionButton: 'bg-blue-600 text-white',
        cancelButton: 'bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300',
        error:
          'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-700/50 text-red-800 dark:text-red-200',
        success:
          'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-700/50 text-green-800 dark:text-green-200',
        warning:
          'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-700/50 text-yellow-800 dark:text-yellow-200',
        info: 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-700/50 text-blue-800 dark:text-blue-200',
      },
    }}
    closeButton
    richColors
  />
);

/**
 * Toast notification helpers.
 *
 * Usage:
 *   import { showToast } from '@/components/Toast';
 *   showToast.success('Operation completed');
 *   showToast.error('Something went wrong');
 *   showToast.info('FYI...');
 *   showToast.warning('Be careful!');
 */
export const showToast = {
  success: (message: string, description?: string) =>
    toast.success(message, { description }),

  error: (message: string, description?: string) =>
    toast.error(message, { description }),

  info: (message: string, description?: string) =>
    toast.info(message, { description }),

  warning: (message: string, description?: string) =>
    toast.warning(message, { description }),

  /** Dismissable loading toast - returns toast ID for dismissing */
  loading: (message: string) => toast.loading(message),

  /** Dismiss a specific toast by ID */
  dismiss: (toastId: string | number) => toast.dismiss(toastId),

  /** Promise-based toast that shows loading/success/error states */
  promise: <T,>(
    promise: Promise<T>,
    messages: { loading: string; success: string; error: string }
  ) => toast.promise(promise, messages),
};

// Re-export the original toast for advanced usage
export { toast };
