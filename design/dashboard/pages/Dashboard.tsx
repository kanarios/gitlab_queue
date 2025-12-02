import React from 'react';
import { MergeRequest, MRStatus } from '../types';
import StatusBadge from '../components/StatusBadge';
import { Play, SkipForward, AlertCircle, GitPullRequest, Flame, Check, MoreVertical, ExternalLink } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface DashboardProps {
  queue: MergeRequest[];
  onSimulateAdvance: () => void;
  onSimulateAdd: () => void;
  onSimulateHotfix: () => void;
}

const Dashboard: React.FC<DashboardProps> = ({ queue, onSimulateAdvance, onSimulateAdd, onSimulateHotfix }) => {
  const activeMR = queue.find(mr => [MRStatus.REBASING, MRStatus.TESTING, MRStatus.MERGING].includes(mr.status));
  const pendingQueue = queue.filter(mr => mr.status === MRStatus.QUEUED && mr.iid !== activeMR?.iid);

  // Helper to determine progress bar width
  const getProgress = (status: MRStatus) => {
    switch (status) {
      case MRStatus.REBASING: return 33;
      case MRStatus.TESTING: return 66;
      case MRStatus.MERGING: return 90;
      default: return 0;
    }
  };

  const getMrUrl = (iid: number) => `https://gitlab.com/gitlab-org/gitlab/-/merge_requests/${iid}`;

  return (
    <div className="space-y-6 md:space-y-8">
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h2 className="text-2xl md:text-3xl font-bold text-slate-900 dark:text-white mb-2">Live Queue</h2>
          <p className="text-sm md:text-base text-slate-500 dark:text-slate-400">Monitoring real-time merge operations for <span className="text-blue-600 dark:text-blue-400 font-mono">my-awesome-project</span></p>
        </div>
        <div className="flex flex-wrap gap-2 w-full md:w-auto">
             {/* Simulation Buttons for interactivity */}
            <button onClick={onSimulateAdd} className="flex-1 md:flex-none px-4 py-2 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-lg text-sm border border-slate-200 dark:border-slate-700 transition-colors shadow-sm whitespace-nowrap">
                + Simulate Add
            </button>
            <button onClick={onSimulateHotfix} className="flex-1 md:flex-none px-4 py-2 bg-orange-50 dark:bg-orange-900/30 hover:bg-orange-100 dark:hover:bg-orange-900/50 text-orange-600 dark:text-orange-400 border border-orange-200 dark:border-orange-700/50 rounded-lg text-sm transition-colors flex items-center justify-center shadow-sm whitespace-nowrap">
                <Flame className="w-4 h-4 mr-2" /> Add Hotfix
            </button>
             <button onClick={onSimulateAdvance} className="flex-1 md:flex-none px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm shadow-lg shadow-blue-500/30 dark:shadow-blue-900/50 flex items-center justify-center transition-all active:scale-95 whitespace-nowrap">
                <Play className="w-4 h-4 mr-2" /> Advance State
            </button>
        </div>
      </div>

      {/* Active Processing Card */}
      <AnimatePresence mode="wait">
      {activeMR ? (
        <motion.div 
            key={activeMR.iid}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="bg-white dark:bg-slate-800/50 backdrop-blur-md rounded-2xl border border-blue-200 dark:border-blue-500/30 p-5 md:p-8 shadow-xl dark:shadow-[0_0_40px_rgba(59,130,246,0.1)] relative overflow-hidden"
        >
            {/* Background Glow */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-blue-100 dark:bg-blue-600/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none"></div>

            <div className="flex flex-col md:flex-row justify-between items-start mb-6 md:mb-8 relative z-10 gap-4">
                <div className="flex flex-col sm:flex-row items-start gap-4 w-full">
                    <img src={activeMR.author.avatar} alt={activeMR.author.name} className="w-14 h-14 md:w-16 md:h-16 rounded-xl border-2 border-slate-200 dark:border-slate-700 shadow-lg" />
                    <div className="w-full">
                        <div className="flex flex-wrap items-center gap-2 mb-1">
                            <a 
                                href={getMrUrl(activeMR.iid)} 
                                target="_blank" 
                                rel="noopener noreferrer" 
                                className="text-blue-600 dark:text-blue-400 font-mono text-lg font-bold hover:underline flex items-center group"
                            >
                                !{activeMR.iid}
                                <ExternalLink className="w-3 h-3 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                            </a>
                            <StatusBadge status={activeMR.status} />
                            {activeMR.isHotfix && (
                                <span className="text-orange-500 flex items-center text-xs font-bold uppercase tracking-wider border border-orange-200 dark:border-orange-500/30 px-2 py-0.5 rounded-full bg-orange-50 dark:bg-orange-500/10">
                                    <Flame className="w-3 h-3 mr-1" /> Hotfix
                                </span>
                            )}
                        </div>
                        <h3 className="text-xl md:text-2xl font-bold text-slate-900 dark:text-white mb-2 leading-tight">{activeMR.title}</h3>
                        <p className="text-sm md:text-base text-slate-500 dark:text-slate-400 flex flex-wrap items-center gap-1">
                            <GitPullRequest className="w-4 h-4 mr-1" />
                            Merging into <span className="text-slate-700 dark:text-slate-200 font-mono bg-slate-100 dark:bg-slate-700/50 px-1 rounded">{activeMR.targetBranch}</span>
                            by {activeMR.author.name}
                        </p>
                    </div>
                </div>
                <div className="flex items-center justify-between w-full md:w-auto md:block md:text-right border-t md:border-t-0 border-slate-100 dark:border-slate-800 pt-4 md:pt-0">
                    <div className="text-sm text-slate-500 dark:text-slate-400 md:mb-1">Duration</div>
                    <div className="font-mono text-lg md:text-xl text-slate-900 dark:text-white">04:21</div>
                </div>
            </div>

            {/* Progress Stepper */}
            <div className="relative pt-2">
                <div className="h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                    <motion.div 
                        className="h-full bg-gradient-to-r from-blue-500 to-purple-600 dark:from-blue-600 dark:to-purple-600"
                        initial={{ width: 0 }}
                        animate={{ width: `${getProgress(activeMR.status)}%` }}
                        transition={{ duration: 0.8, ease: "easeInOut" }}
                    />
                </div>
                <div className="flex justify-between mt-4 text-[10px] sm:text-sm font-medium">
                    <div className={`${activeMR.status === MRStatus.REBASING ? 'text-blue-600 dark:text-blue-400 animate-pulse' : 'text-slate-400 dark:text-slate-500'}`}>1. Rebasing</div>
                    <div className={`${activeMR.status === MRStatus.TESTING ? 'text-purple-600 dark:text-purple-400 animate-pulse' : 'text-slate-400 dark:text-slate-500'}`}>2. Testing</div>
                    <div className={`${activeMR.status === MRStatus.MERGING ? 'text-orange-600 dark:text-orange-400 animate-pulse' : 'text-slate-400 dark:text-slate-500'}`}>3. Merging</div>
                    <div className="text-slate-400 dark:text-slate-600">4. Done</div>
                </div>
            </div>
        </motion.div>
      ) : (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="bg-slate-50 dark:bg-slate-800/30 border border-slate-200 dark:border-slate-700 border-dashed rounded-2xl p-8 md:p-12 text-center"
        >
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-slate-100 dark:bg-slate-800 mb-4">
                  <Check className="w-8 h-8 text-slate-400 dark:text-slate-500" />
              </div>
              <h3 className="text-xl font-medium text-slate-700 dark:text-slate-300">Queue is empty</h3>
              <p className="text-slate-500 mt-2">No active merge requests processing right now.</p>
          </motion.div>
      )}
      </AnimatePresence>

      {/* Up Next List */}
      <div>
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-4 flex items-center">
            <SkipForward className="w-5 h-5 mr-2 text-slate-400" />
            Up Next ({pendingQueue.length})
        </h3>
        
        <div className="grid gap-3">
            <AnimatePresence>
            {pendingQueue.map((mr, index) => (
                <motion.div
                    key={mr.iid}
                    layout
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: 20 }}
                    className={`bg-white dark:bg-slate-800 border ${mr.isHotfix ? 'border-orange-200 dark:border-orange-500/40 bg-orange-50 dark:bg-orange-900/10' : 'border-slate-200 dark:border-slate-700'} rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 sm:gap-0 group hover:border-blue-300 dark:hover:border-slate-600 transition-colors shadow-sm`}
                >
                    <div className="flex items-start space-x-4 w-full sm:w-auto">
                        <div className="text-slate-400 dark:text-slate-500 font-mono w-6 text-center text-sm pt-1 sm:pt-0">#{index + 1}</div>
                        <img src={mr.author.avatar} className="w-10 h-10 rounded-full border border-slate-200 dark:border-slate-700 shrink-0" alt="avatar" />
                        <div className="min-w-0 flex-1">
                            <div className="flex items-center space-x-2">
                                <span className="text-slate-900 dark:text-slate-200 font-medium truncate block">{mr.title}</span>
                                {mr.isHotfix && <Flame className="w-4 h-4 text-orange-500 fill-orange-500/20 shrink-0" />}
                            </div>
                            <div className="text-sm text-slate-500 flex flex-wrap items-center gap-x-2 gap-y-1 mt-0.5">
                                <a 
                                    href={getMrUrl(mr.iid)}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="font-mono text-blue-600 dark:text-blue-400 hover:underline"
                                >
                                    !{mr.iid}
                                </a>
                                <span className="hidden sm:inline">•</span>
                                <span>{mr.author.name}</span>
                                <span className="hidden sm:inline">•</span>
                                <span className="text-slate-400 dark:text-slate-600 text-xs">Queued 20m ago</span>
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center justify-between w-full sm:w-auto sm:space-x-4 pl-14 sm:pl-0">
                        <div className="flex flex-wrap gap-1">
                            {mr.labels.map(l => (
                                <span key={l} className="text-[10px] uppercase bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 px-1.5 py-0.5 rounded border border-slate-200 dark:border-slate-600">{l}</span>
                            ))}
                        </div>
                        <button className="text-slate-400 hover:text-slate-600 dark:hover:text-white p-2">
                            <MoreVertical className="w-4 h-4" />
                        </button>
                    </div>
                </motion.div>
            ))}
            </AnimatePresence>
            {pendingQueue.length === 0 && (
                <div className="text-center py-8 text-slate-500 italic">No other items in queue.</div>
            )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;