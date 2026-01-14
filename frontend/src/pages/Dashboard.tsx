import React, { useState, useEffect } from 'react';
import { MergeRequest, MRStatus, WebSocketState } from '../types';
import StatusBadge from '../components/StatusBadge';
import ConnectionIndicator from '../components/ConnectionIndicator';
import { DashboardSkeleton } from '../components/LoadingSkeleton';
import { SkipForward, GitPullRequest, Flame, Check, MoreVertical, ExternalLink } from 'lucide-react';
import { SafeMotionDiv, AnimatePresence } from '../components/SafeMotion';

interface DashboardProps {
  queue: MergeRequest[];
  wsState: WebSocketState;
  onReconnect: () => void;
}

/**
 * Calculate duration string from started_at timestamp.
 */
const calculateDuration = (startedAt: string | null): string => {
  if (!startedAt) return '--:--';
  const start = new Date(startedAt).getTime();
  const now = Date.now();
  const diffSeconds = Math.floor((now - start) / 1000);
  if (diffSeconds < 0) return '--:--';
  const minutes = Math.floor(diffSeconds / 60);
  const seconds = diffSeconds % 60;
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
};

const DEFAULT_AVATAR = 'https://www.gravatar.com/avatar/?d=mp';

const Dashboard: React.FC<DashboardProps> = ({ queue, wsState, onReconnect }) => {
  const activeMR = queue.find((mr) =>
    (['rebasing', 'testing', 'merging'] as MRStatus[]).includes(mr.status)
  );
  const pendingQueue = queue.filter(
    (mr) => mr.status === 'queued' && mr.mr_iid !== activeMR?.mr_iid
  );

  // Duration state with live updates
  const [duration, setDuration] = useState('--:--');

  useEffect(() => {
    if (!activeMR?.started_at) {
      setDuration('--:--');
      return;
    }

    // Initial calculation
    setDuration(calculateDuration(activeMR.started_at));

    // Update every second
    const interval = setInterval(() => {
      setDuration(calculateDuration(activeMR.started_at));
    }, 1000);

    return () => clearInterval(interval);
  }, [activeMR?.started_at]);

  const getProgress = (status: MRStatus) => {
    switch (status) {
      case 'rebasing':
        return 33;
      case 'testing':
        return 66;
      case 'merging':
        return 90;
      default:
        return 0;
    }
  };

  const gitlabUrl = import.meta.env.VITE_GITLAB_URL || 'https://gitlab.com';
  const getMrUrl = (iid: number) => `${gitlabUrl}/project/-/merge_requests/${iid}`;

  // Show loading skeleton during initial connection
  if (wsState === 'connecting') {
    return <DashboardSkeleton />;
  }

  return (
    <div className="space-y-6 md:space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h2 className="text-2xl md:text-3xl font-bold text-slate-900 dark:text-white mb-2">
            Live Queue
          </h2>
          <p className="text-sm md:text-base text-slate-500 dark:text-slate-400">
            Monitoring real-time merge operations
          </p>
        </div>
        <ConnectionIndicator state={wsState} onReconnect={onReconnect} />
      </div>

      {/* Active Processing Card */}
      <AnimatePresence mode="wait">
        {activeMR ? (
          <SafeMotionDiv
            key={activeMR.mr_iid}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="bg-white dark:bg-slate-800/50 backdrop-blur-md rounded-2xl border border-blue-200 dark:border-blue-500/30 p-5 md:p-8 shadow-xl dark:shadow-[0_0_40px_rgba(59,130,246,0.1)] relative overflow-hidden"
            role="region"
            aria-label={`Active merge request: ${activeMR.title}`}
          >
            {/* Background Glow */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-blue-100 dark:bg-blue-600/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none"></div>

            <div className="flex flex-col md:flex-row justify-between items-start mb-6 md:mb-8 relative z-10 gap-4">
              <div className="flex flex-col sm:flex-row items-start gap-4 w-full">
                <img
                  src={activeMR.author.avatar_url || DEFAULT_AVATAR}
                  alt={activeMR.author.name}
                  className="w-14 h-14 md:w-16 md:h-16 rounded-xl border-2 border-slate-200 dark:border-slate-700 shadow-lg"
                />
                <div className="w-full">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    <a
                      href={getMrUrl(activeMR.mr_iid)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 dark:text-blue-400 font-mono text-lg font-bold hover:underline flex items-center group focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none rounded"
                      aria-label={`Open merge request !${activeMR.mr_iid} in GitLab (opens in new tab)`}
                    >
                      !{activeMR.mr_iid}
                      <ExternalLink className="w-3 h-3 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" aria-hidden="true" />
                    </a>
                    <StatusBadge status={activeMR.status} />
                    {activeMR.is_hotfix && (
                      <span className="text-orange-500 flex items-center text-xs font-bold uppercase tracking-wider border border-orange-200 dark:border-orange-500/30 px-2 py-0.5 rounded-full bg-orange-50 dark:bg-orange-500/10" role="status" aria-label="Hotfix priority">
                        <Flame className="w-3 h-3 mr-1" aria-hidden="true" /> Hotfix
                      </span>
                    )}
                  </div>
                  <h3 className="text-xl md:text-2xl font-bold text-slate-900 dark:text-white mb-2 leading-tight">
                    {activeMR.title}
                  </h3>
                  <p className="text-sm md:text-base text-slate-500 dark:text-slate-400 flex flex-wrap items-center gap-1">
                    <GitPullRequest className="w-4 h-4 mr-1" aria-hidden="true" />
                    Merging into{' '}
                    <span className="text-slate-700 dark:text-slate-200 font-mono bg-slate-100 dark:bg-slate-700/50 px-1 rounded">
                      {activeMR.target_branch}
                    </span>
                    by {activeMR.author.name}
                  </p>
                </div>
              </div>
              <div className="flex items-center justify-between w-full md:w-auto md:block md:text-right border-t md:border-t-0 border-slate-100 dark:border-slate-800 pt-4 md:pt-0">
                <div className="text-sm text-slate-500 dark:text-slate-400 md:mb-1">Duration</div>
                <div className="font-mono text-lg md:text-xl text-slate-900 dark:text-white">
                  {duration}
                </div>
              </div>
            </div>

            {/* Progress Stepper */}
            <div className="relative pt-2">
              <div
                className="h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden"
                role="progressbar"
                aria-valuenow={getProgress(activeMR.status)}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`Merge progress: ${activeMR.status}`}
              >
                <SafeMotionDiv
                  className="h-full bg-gradient-to-r from-blue-500 to-purple-600 dark:from-blue-600 dark:to-purple-600"
                  initial={{ width: 0 }}
                  animate={{ width: `${getProgress(activeMR.status)}%` }}
                  transition={{ duration: 0.8, ease: 'easeInOut' }}
                />
              </div>
              <div className="flex justify-between mt-4 text-[10px] sm:text-sm font-medium">
                <div
                  className={`${activeMR.status === 'rebasing' ? 'text-blue-600 dark:text-blue-400 animate-pulse' : 'text-slate-400 dark:text-slate-500'}`}
                >
                  1. Rebasing
                </div>
                <div
                  className={`${activeMR.status === 'testing' ? 'text-purple-600 dark:text-purple-400 animate-pulse' : 'text-slate-400 dark:text-slate-500'}`}
                >
                  2. Testing
                </div>
                <div
                  className={`${activeMR.status === 'merging' ? 'text-orange-600 dark:text-orange-400 animate-pulse' : 'text-slate-400 dark:text-slate-500'}`}
                >
                  3. Merging
                </div>
                <div className="text-slate-400 dark:text-slate-600">4. Done</div>
              </div>
            </div>
          </SafeMotionDiv>
        ) : (
          <SafeMotionDiv
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="bg-slate-50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-700 border-dashed rounded-2xl p-8 md:p-12 text-center"
            role="status"
            aria-label="Queue is empty"
          >
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-100 dark:bg-slate-800 mb-4">
              <Check className="w-8 h-8 text-slate-400 dark:text-slate-500" aria-hidden="true" />
            </div>
            <h3 className="text-xl font-medium text-slate-700 dark:text-slate-300">
              Queue is empty
            </h3>
            <p className="text-slate-500 mt-2">No active merge requests processing right now.</p>
          </SafeMotionDiv>
        )}
      </AnimatePresence>

      {/* Up Next List */}
      <section aria-labelledby="up-next-heading">
        <h3 id="up-next-heading" className="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center">
          <SkipForward className="w-5 h-5 mr-2 text-slate-400" aria-hidden="true" />
          Up Next ({pendingQueue.length})
        </h3>

        <div className="grid gap-3" role="list" aria-label="Pending merge requests">
          <AnimatePresence>
            {pendingQueue.map((mr, index) => (
              <SafeMotionDiv
                key={mr.mr_iid}
                layout
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className={`bg-white dark:bg-slate-800 border ${mr.is_hotfix ? 'border-orange-200 dark:border-orange-500/40 bg-orange-50 dark:bg-orange-900/10' : 'border-slate-200 dark:border-slate-700'} rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 sm:gap-0 group hover:border-blue-300 dark:hover:border-slate-600 transition-colors shadow-sm`}
                role="listitem"
                aria-label={`Position ${index + 1}: ${mr.title} by ${mr.author.name}${mr.is_hotfix ? ', Hotfix priority' : ''}`}
              >
                <div className="flex items-start space-x-4 w-full sm:w-auto">
                  <div className="text-slate-400 dark:text-slate-500 font-mono w-6 text-center text-sm pt-1 sm:pt-0">
                    #{index + 1}
                  </div>
                  <img
                    src={mr.author.avatar_url || DEFAULT_AVATAR}
                    className="w-10 h-10 rounded-full border border-slate-200 dark:border-slate-700 shrink-0"
                    alt="avatar"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center space-x-2">
                      <span className="text-slate-900 dark:text-slate-200 font-medium truncate block">
                        {mr.title}
                      </span>
                      {mr.is_hotfix && (
                        <Flame className="w-4 h-4 text-orange-500 fill-orange-500/20 shrink-0" aria-hidden="true" />
                      )}
                    </div>
                    <div className="text-sm text-slate-500 flex flex-wrap items-center gap-x-2 gap-y-1 mt-0.5">
                      <a
                        href={getMrUrl(mr.mr_iid)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono text-blue-600 dark:text-blue-400 hover:underline focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none rounded"
                        aria-label={`Open merge request !${mr.mr_iid} in GitLab (opens in new tab)`}
                      >
                        !{mr.mr_iid}
                      </a>
                      <span className="hidden sm:inline">•</span>
                      <span>{mr.author.name}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center justify-between w-full sm:w-auto sm:space-x-4 pl-14 sm:pl-0">
                  <div className="flex flex-wrap gap-1">
                    {mr.labels.map((l) => (
                      <span
                        key={l}
                        className="text-[10px] uppercase bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 px-1.5 py-0.5 rounded border border-slate-200 dark:border-slate-600"
                      >
                        {l}
                      </span>
                    ))}
                  </div>
                  <button
                    className="text-slate-400 hover:text-slate-600 dark:hover:text-white p-2 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none rounded"
                    aria-label={`More options for merge request !${mr.mr_iid}`}
                  >
                    <MoreVertical className="w-4 h-4" aria-hidden="true" />
                  </button>
                </div>
              </SafeMotionDiv>
            ))}
          </AnimatePresence>
          {pendingQueue.length === 0 && (
            <div className="text-center py-8 text-slate-500 italic" role="status">No other items in queue.</div>
          )}
        </div>
      </section>
    </div>
  );
};

export default Dashboard;
