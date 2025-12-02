import React, { useState } from 'react';
import { MergeRequest, MRStatus } from '../types';
import StatusBadge from '../components/StatusBadge';
import { Search, Calendar, Filter, ExternalLink, AlertTriangle, XCircle, FileWarning } from 'lucide-react';
import { motion } from 'framer-motion';

interface HistoryProps {
  history: MergeRequest[];
}

const History: React.FC<HistoryProps> = ({ history }) => {
  const [filter, setFilter] = useState('');

  const filteredHistory = history.filter(mr => 
    mr.title.toLowerCase().includes(filter.toLowerCase()) || 
    mr.author.name.toLowerCase().includes(filter.toLowerCase()) ||
    mr.iid.toString().includes(filter)
  );

  const getMrUrl = (iid: number) => `https://gitlab.com/gitlab-org/gitlab/-/merge_requests/${iid}`;

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <h2 className="text-2xl md:text-3xl font-bold text-slate-900 dark:text-white">History Log</h2>
        
        <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-3">
          <div className="relative w-full sm:w-auto">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input 
              type="text" 
              placeholder="Search MRs..." 
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="w-full sm:w-64 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white pl-10 pr-4 py-2 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm"
            />
          </div>
          <button className="flex items-center justify-center space-x-2 px-3 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-slate-600 dark:text-slate-300 text-sm hover:bg-slate-50 dark:hover:bg-slate-700 shadow-sm transition-colors w-full sm:w-auto">
            <Filter className="w-4 h-4" />
            <span>Filter</span>
          </button>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden backdrop-blur-sm shadow-sm">
        <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-500 dark:text-slate-400 whitespace-nowrap md:whitespace-normal">
            <thead className="bg-slate-50 dark:bg-slate-900/50 text-slate-700 dark:text-slate-200 uppercase text-xs font-semibold">
                <tr>
                <th className="px-6 py-4">MR</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Title & Details</th>
                <th className="px-6 py-4">Author</th>
                <th className="px-6 py-4">Pipeline</th>
                <th className="px-6 py-4">Finished At</th>
                </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {filteredHistory.map((mr) => (
                <motion.tr 
                    key={mr.iid}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                >
                    <td className="px-6 py-4 align-top">
                    <a 
                        href={getMrUrl(mr.iid)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-mono text-blue-600 dark:text-blue-400 hover:underline flex items-center group w-fit mt-1"
                    >
                        !{mr.iid}
                        <ExternalLink className="w-3 h-3 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </a>
                    </td>
                    <td className="px-6 py-4 align-top">
                    <div className="mt-1">
                        <StatusBadge status={mr.status} />
                    </div>
                    </td>
                    <td className="px-6 py-4 max-w-md align-top whitespace-normal">
                    <div className="text-slate-900 dark:text-white font-medium line-clamp-2 mt-1" title={mr.title}>
                        {mr.title}
                    </div>
                    
                    {(mr.status === MRStatus.FAILED || mr.status === MRStatus.CONFLICT || mr.failureReason) && (
                        <div className="mt-3 space-y-2 min-w-[200px]">
                        {mr.failureReason && (
                            <div className={`flex items-start gap-2 p-2.5 rounded-lg border text-xs ${
                                mr.status === MRStatus.CONFLICT 
                                    ? 'bg-orange-50 dark:bg-orange-900/10 border-orange-100 dark:border-orange-900/20' 
                                    : 'bg-red-50 dark:bg-red-900/10 border-red-100 dark:border-red-900/20'
                            }`}>
                            {mr.status === MRStatus.CONFLICT ? (
                                <AlertTriangle className="w-4 h-4 text-orange-600 dark:text-orange-400 shrink-0 mt-0.5" />
                            ) : (
                                <XCircle className="w-4 h-4 text-red-600 dark:text-red-400 shrink-0 mt-0.5" />
                            )}
                            <div>
                                <span className={`font-semibold block mb-0.5 ${
                                    mr.status === MRStatus.CONFLICT ? 'text-orange-800 dark:text-orange-300' : 'text-red-800 dark:text-red-300'
                                }`}>
                                {mr.status === MRStatus.CONFLICT ? 'Merge Conflict' : 'Failure Reason'}
                                </span>
                                <span className={`${
                                    mr.status === MRStatus.CONFLICT ? 'text-orange-700 dark:text-orange-400' : 'text-red-700 dark:text-red-400'
                                } leading-relaxed break-words`}>
                                {mr.failureReason}
                                </span>
                            </div>
                            </div>
                        )}

                        {mr.status === MRStatus.FAILED && mr.pipeline?.jobs_failed && mr.pipeline.jobs_failed.length > 0 && (
                            <div className="ml-1 pl-3 border-l-2 border-slate-200 dark:border-slate-700">
                            <div className="text-xs text-slate-500 dark:text-slate-400 mb-1.5 flex items-center">
                                <span className="font-medium">Failed Pipeline Jobs</span>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {mr.pipeline.jobs_failed.map(job => (
                                    <span key={job} className="inline-flex items-center px-2 py-1 rounded bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-[10px] font-mono text-red-600 dark:text-red-400">
                                    {job}
                                    </span>
                                ))}
                            </div>
                            </div>
                        )}
                        </div>
                    )}
                    </td>
                    <td className="px-6 py-4 align-top">
                    <div className="flex items-center space-x-2 mt-1">
                        <img src={mr.author.avatar} alt="" className="w-6 h-6 rounded-full border border-slate-200 dark:border-slate-700" />
                        <span>{mr.author.name}</span>
                    </div>
                    </td>
                    <td className="px-6 py-4 align-top">
                    {mr.pipeline ? (
                        <a href="#" className="flex items-center text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors mt-1">
                        <span className="font-mono mr-1">#{mr.pipeline.id}</span>
                        <ExternalLink className="w-3 h-3 opacity-50" />
                        </a>
                    ) : (
                        <span className="text-slate-400 dark:text-slate-600 mt-1 inline-block">-</span>
                    )}
                    </td>
                    <td className="px-6 py-4 align-top">
                    <div className="flex items-center space-x-1.5 mt-1">
                        <Calendar className="w-3 h-3 text-slate-400 dark:text-slate-500" />
                        <span>{new Date(mr.finishedAt || mr.queuedAt).toLocaleDateString()}</span>
                    </div>
                    </td>
                </motion.tr>
                ))}
                {filteredHistory.length === 0 && (
                <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                    No records found matching your search.
                    </td>
                </tr>
                )}
            </tbody>
            </table>
        </div>
      </div>
    </div>
  );
};

export default History;