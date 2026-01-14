import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { MergeRequest } from '../types';
import { getHistory } from '../api/history';
import type { Pagination } from '../api/types';
import StatusBadge from '../components/StatusBadge';
import ErrorDisplay from '../components/ErrorDisplay';
import { HistoryTableSkeleton } from '../components/LoadingSkeleton';
import {
  Search,
  Calendar,
  ExternalLink,
  AlertTriangle,
  XCircle,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { SafeMotionTr } from '../components/SafeMotion';

const DEFAULT_AVATAR = 'https://www.gravatar.com/avatar/?d=mp';
const PER_PAGE = 20;

const History: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();

  // Data state
  const [history, setHistory] = useState<MergeRequest[]>([]);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter state - initialized from URL
  const [search, setSearch] = useState(() => searchParams.get('search') || '');
  const [debouncedSearch, setDebouncedSearch] = useState(search);
  const [statusFilter, setStatusFilter] = useState(() => searchParams.get('status') || '');
  const [page, setPage] = useState(() => parseInt(searchParams.get('page') || '1', 10));

  // Track if initial load is done to prevent double URL updates
  const initialLoadDone = useRef(false);

  const gitlabUrl = import.meta.env.VITE_GITLAB_URL || 'https://gitlab.com';
  const getMrUrl = (iid: number) => `${gitlabUrl}/project/-/merge_requests/${iid}`;

  // Debounce search input (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      if (debouncedSearch !== search) {
        setDebouncedSearch(search);
        setPage(1); // Reset to page 1 on search change
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [search, debouncedSearch]);

  // Sync filters to URL
  useEffect(() => {
    if (!initialLoadDone.current) {
      initialLoadDone.current = true;
      return;
    }

    const params: Record<string, string> = {};
    if (debouncedSearch) params.search = debouncedSearch;
    if (statusFilter) params.status = statusFilter;
    if (page > 1) params.page = page.toString();
    setSearchParams(params, { replace: true });
  }, [debouncedSearch, statusFilter, page, setSearchParams]);

  // Fetch data
  useEffect(() => {
    const controller = new AbortController();

    async function fetchHistory() {
      setLoading(true);
      setError(null);

      const result = await getHistory({
        page,
        per_page: PER_PAGE,
        search: debouncedSearch || undefined,
        status: statusFilter || undefined,
        signal: controller.signal,
      });

      if (result.success) {
        setHistory(result.data.items);
        setPagination(result.data.pagination);
        setLoading(false);
      } else if (result.error.type !== 'network_error' || !controller.signal.aborted) {
        // Only set error if not aborted
        setError(result.error.message);
        setLoading(false);
      }
    }

    fetchHistory();

    return () => controller.abort();
  }, [page, debouncedSearch, statusFilter]);

  const handleStatusChange = (value: string) => {
    setStatusFilter(value);
    setPage(1);
  };

  const handleRetry = () => {
    // Trigger refetch by toggling a dependency
    setPage((p) => p);
    setError(null);
    setLoading(true);
    // Force refetch
    const refetch = async () => {
      const result = await getHistory({
        page,
        per_page: PER_PAGE,
        search: debouncedSearch || undefined,
        status: statusFilter || undefined,
      });

      if (result.success) {
        setHistory(result.data.items);
        setPagination(result.data.pagination);
      } else {
        setError(result.error.message);
      }
      setLoading(false);
    };
    refetch();
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <h2 className="text-2xl md:text-3xl font-bold text-slate-900 dark:text-white">History Log</h2>

        <div className="flex flex-col sm:flex-row space-y-2 sm:space-y-0 sm:space-x-3">
          <div className="relative w-full sm:w-auto">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" aria-hidden="true" />
            <input
              type="search"
              placeholder="Search MRs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full sm:w-64 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white pl-10 pr-4 py-2 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500 shadow-sm"
              aria-label="Search merge requests"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => handleStatusChange(e.target.value)}
            className="px-3 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-white rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 shadow-sm cursor-pointer"
            aria-label="Filter by status"
          >
            <option value="">All Statuses</option>
            <option value="merged">Merged</option>
            <option value="failed">Failed</option>
            <option value="conflict">Conflict</option>
            <option value="timeout">Timeout</option>
          </select>
        </div>
      </div>

      <div className="bg-white dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden backdrop-blur-sm shadow-sm">
        {/* Loading State */}
        {loading && <HistoryTableSkeleton rows={5} />}

        {/* Error State */}
        {error && !loading && (
          <ErrorDisplay
            error={error}
            title="Failed to load history"
            variant="full"
            onRetry={handleRetry}
          />
        )}

        {/* Data Table */}
        {!loading && !error && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-500 dark:text-slate-400 whitespace-nowrap md:whitespace-normal" aria-label="Merge request history">
                <thead className="bg-slate-50 dark:bg-slate-900/50 text-slate-700 dark:text-slate-200 uppercase text-xs font-semibold">
                  <tr>
                    <th scope="col" className="px-6 py-4">MR</th>
                    <th scope="col" className="px-6 py-4">Status</th>
                    <th scope="col" className="px-6 py-4">Title & Details</th>
                    <th scope="col" className="px-6 py-4">Author</th>
                    <th scope="col" className="px-6 py-4">Pipeline</th>
                    <th scope="col" className="px-6 py-4">Finished At</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {history.map((mr) => (
                    <SafeMotionTr
                      key={mr.mr_iid}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                    >
                      <td className="px-6 py-4 align-top">
                        <a
                          href={getMrUrl(mr.mr_iid)}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-mono text-blue-600 dark:text-blue-400 hover:underline flex items-center group w-fit mt-1 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none rounded"
                          aria-label={`Open merge request !${mr.mr_iid} in GitLab (opens in new tab)`}
                        >
                          !{mr.mr_iid}
                          <ExternalLink className="w-3 h-3 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" aria-hidden="true" />
                        </a>
                      </td>
                      <td className="px-6 py-4 align-top">
                        <div className="mt-1">
                          <StatusBadge status={mr.status} />
                        </div>
                      </td>
                      <td className="px-6 py-4 max-w-md align-top whitespace-normal">
                        <div
                          className="text-slate-900 dark:text-white font-medium line-clamp-2 mt-1"
                          title={mr.title}
                        >
                          {mr.title}
                        </div>

                        {(mr.status === 'failed' || mr.status === 'conflict' || mr.failure_reason) && (
                          <div className="mt-3 space-y-2 min-w-[200px]">
                            {mr.failure_reason && (
                              <div
                                className={`flex items-start gap-2 p-2.5 rounded-lg border text-xs ${
                                  mr.status === 'conflict'
                                    ? 'bg-orange-50 dark:bg-orange-900/10 border-orange-100 dark:border-orange-900/20'
                                    : 'bg-red-50 dark:bg-red-900/10 border-red-100 dark:border-red-900/20'
                                }`}
                              >
                                {mr.status === 'conflict' ? (
                                  <AlertTriangle className="w-4 h-4 text-orange-600 dark:text-orange-400 shrink-0 mt-0.5" aria-hidden="true" />
                                ) : (
                                  <XCircle className="w-4 h-4 text-red-600 dark:text-red-400 shrink-0 mt-0.5" aria-hidden="true" />
                                )}
                                <div>
                                  <span
                                    className={`font-semibold block mb-0.5 ${
                                      mr.status === 'conflict'
                                        ? 'text-orange-800 dark:text-orange-300'
                                        : 'text-red-800 dark:text-red-300'
                                    }`}
                                  >
                                    {mr.status === 'conflict' ? 'Merge Conflict' : 'Failure Reason'}
                                  </span>
                                  <span
                                    className={`${
                                      mr.status === 'conflict'
                                        ? 'text-orange-700 dark:text-orange-400'
                                        : 'text-red-700 dark:text-red-400'
                                    } leading-relaxed break-words`}
                                  >
                                    {mr.failure_reason}
                                  </span>
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 align-top">
                        <div className="flex items-center space-x-2 mt-1">
                          <img
                            src={mr.author.avatar_url || DEFAULT_AVATAR}
                            alt=""
                            className="w-6 h-6 rounded-full border border-slate-200 dark:border-slate-700"
                          />
                          <span>{mr.author.name}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 align-top">
                        {mr.pipeline ? (
                          <a
                            href={`${gitlabUrl}/project/-/pipelines/${mr.pipeline.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors mt-1 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none rounded"
                            aria-label={`View pipeline #${mr.pipeline.id} in GitLab (opens in new tab)`}
                          >
                            <span className="font-mono mr-1">#{mr.pipeline.id}</span>
                            <ExternalLink className="w-3 h-3 opacity-50" aria-hidden="true" />
                          </a>
                        ) : (
                          <span className="text-slate-400 dark:text-slate-600 mt-1 inline-block" aria-label="No pipeline">-</span>
                        )}
                      </td>
                      <td className="px-6 py-4 align-top">
                        <div className="flex items-center space-x-1.5 mt-1">
                          <Calendar className="w-3 h-3 text-slate-400 dark:text-slate-500" aria-hidden="true" />
                          <span>
                            {new Date(mr.finished_at || mr.queued_at).toLocaleDateString()}
                          </span>
                        </div>
                      </td>
                    </SafeMotionTr>
                  ))}
                  {history.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-6 py-12 text-center text-slate-500">
                        {debouncedSearch || statusFilter
                          ? 'No records found matching your filters.'
                          : 'No history records yet.'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {pagination && pagination.total_pages > 1 && (
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4 px-6 py-4 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/30">
                <div className="text-sm text-slate-500 dark:text-slate-400">
                  Showing{' '}
                  <span className="font-medium text-slate-700 dark:text-slate-200">
                    {(pagination.page - 1) * pagination.per_page + 1}
                  </span>{' '}
                  -{' '}
                  <span className="font-medium text-slate-700 dark:text-slate-200">
                    {Math.min(pagination.page * pagination.per_page, pagination.total)}
                  </span>{' '}
                  of{' '}
                  <span className="font-medium text-slate-700 dark:text-slate-200">
                    {pagination.total}
                  </span>{' '}
                  results
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={pagination.page <= 1}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
                    aria-label="Previous page"
                  >
                    <ChevronLeft className="w-4 h-4" aria-hidden="true" />
                    Previous
                  </button>
                  <span className="px-3 py-1.5 text-sm text-slate-600 dark:text-slate-400" aria-live="polite">
                    Page {pagination.page} of {pagination.total_pages}
                  </span>
                  <button
                    onClick={() => setPage((p) => Math.min(pagination.total_pages, p + 1))}
                    disabled={pagination.page >= pagination.total_pages}
                    className="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
                    aria-label="Next page"
                  >
                    Next
                    <ChevronRight className="w-4 h-4" aria-hidden="true" />
                  </button>
                </div>
              </div>
            )}

            {/* Single page indicator */}
            {pagination && pagination.total > 0 && pagination.total_pages === 1 && (
              <div className="px-6 py-3 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/30">
                <div className="text-sm text-slate-500 dark:text-slate-400">
                  Showing all{' '}
                  <span className="font-medium text-slate-700 dark:text-slate-200">
                    {pagination.total}
                  </span>{' '}
                  {pagination.total === 1 ? 'result' : 'results'}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default History;
