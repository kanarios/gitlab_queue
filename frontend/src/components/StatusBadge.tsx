import React from 'react';
import { MRStatus } from '../types';
import { CheckCircle2, XCircle, Loader2, Clock, AlertTriangle } from 'lucide-react';

interface StatusBadgeProps {
  status: MRStatus;
  animate?: boolean;
}

const statusConfig: Record<MRStatus, { color: string; icon: React.ReactNode; label: string }> = {
  queued: {
    color:
      'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-700 dark:text-slate-300 dark:border-slate-600',
    icon: <Clock className="w-3 h-3" aria-hidden="true" />,
    label: 'Queued',
  },
  rebasing: {
    color:
      'bg-blue-50 text-blue-600 border-blue-200 dark:bg-blue-900/40 dark:text-blue-300 dark:border-blue-700/50',
    icon: <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" />,
    label: 'Rebasing',
  },
  testing: {
    color:
      'bg-purple-50 text-purple-600 border-purple-200 dark:bg-purple-900/40 dark:text-purple-300 dark:border-purple-700/50',
    icon: <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" />,
    label: 'Testing',
  },
  merging: {
    color:
      'bg-orange-50 text-orange-600 border-orange-200 dark:bg-orange-900/40 dark:text-orange-300 dark:border-orange-700/50',
    icon: <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" />,
    label: 'Merging',
  },
  merged: {
    color:
      'bg-green-50 text-green-600 border-green-200 dark:bg-green-900/40 dark:text-green-300 dark:border-green-700/50',
    icon: <CheckCircle2 className="w-3 h-3" aria-hidden="true" />,
    label: 'Merged',
  },
  failed: {
    color:
      'bg-red-50 text-red-600 border-red-200 dark:bg-red-900/40 dark:text-red-300 dark:border-red-700/50',
    icon: <XCircle className="w-3 h-3" aria-hidden="true" />,
    label: 'Failed',
  },
  conflict: {
    color:
      'bg-yellow-50 text-yellow-600 border-yellow-200 dark:bg-yellow-900/40 dark:text-yellow-300 dark:border-yellow-700/50',
    icon: <AlertTriangle className="w-3 h-3" aria-hidden="true" />,
    label: 'Conflict',
  },
  timeout: {
    color:
      'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-700 dark:text-slate-300 dark:border-slate-600',
    icon: <Clock className="w-3 h-3" aria-hidden="true" />,
    label: 'Timeout',
  },
  removed: {
    color:
      'bg-slate-100 text-slate-500 border-slate-200 dark:bg-slate-800 dark:text-slate-500 dark:border-slate-700',
    icon: <XCircle className="w-3 h-3" aria-hidden="true" />,
    label: 'Removed',
  },
};

const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const config = statusConfig[status] || statusConfig.queued;

  return (
    <span
      role="status"
      aria-label={`Status: ${config.label}`}
      className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${config.color} shadow-sm backdrop-blur-sm`}
    >
      {config.icon}
      <span>{config.label}</span>
    </span>
  );
};

export default StatusBadge;
