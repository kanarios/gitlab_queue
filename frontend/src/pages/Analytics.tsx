import { useState, useEffect, useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { Clock, GitMerge, TrendingUp, Activity } from 'lucide-react';
import { getSummary, getHourly, getOutcomes, getFailureReasons } from '../api/analytics';
import ErrorDisplay from '../components/ErrorDisplay';
import { KPICardSkeleton, ChartSkeleton } from '../components/LoadingSkeleton';
import type {
  AnalyticsSummary,
  HourlyDataPoint,
  Outcome,
  FailureReason,
} from '../api/types';

type DaysPeriod = 7 | 30 | 90;

interface LoadingState {
  summary: boolean;
  hourly: boolean;
  outcomes: boolean;
  failures: boolean;
}

interface ErrorState {
  summary: string | null;
  hourly: string | null;
  outcomes: string | null;
  failures: string | null;
}

const COLORS = ['#22c55e', '#ef4444', '#eab308', '#3b82f6'];
const OUTCOME_COLORS: Record<string, string> = {
  merged: '#22c55e',
  failed: '#ef4444',
  conflict: '#eab308',
  timeout: '#3b82f6',
};

const Analytics: React.FC = () => {
  // API data state
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [hourlyData, setHourlyData] = useState<HourlyDataPoint[]>([]);
  const [outcomes, setOutcomes] = useState<Outcome[]>([]);
  const [failureReasons, setFailureReasons] = useState<FailureReason[]>([]);

  // UI state
  const [selectedDays, setSelectedDays] = useState<DaysPeriod>(7);
  const [loading, setLoading] = useState<LoadingState>({
    summary: true,
    hourly: true,
    outcomes: true,
    failures: true,
  });
  const [errors, setErrors] = useState<ErrorState>({
    summary: null,
    hourly: null,
    outcomes: null,
    failures: null,
  });

  // Fetch all analytics data in parallel
  useEffect(() => {
    const controller = new AbortController();

    async function fetchAllAnalytics() {
      // Reset loading states
      setLoading({ summary: true, hourly: true, outcomes: true, failures: true });
      setErrors({ summary: null, hourly: null, outcomes: null, failures: null });

      // Map days to hours for hourly endpoint
      const hoursMap: Record<DaysPeriod, number> = { 7: 24, 30: 72, 90: 168 };
      const hours = hoursMap[selectedDays];

      // Fetch all 4 endpoints in parallel
      const [summaryResult, hourlyResult, outcomesResult, failuresResult] = await Promise.all([
        getSummary({ days: selectedDays, signal: controller.signal }),
        getHourly({ hours, signal: controller.signal }),
        getOutcomes({ days: selectedDays, signal: controller.signal }),
        getFailureReasons({ days: selectedDays, signal: controller.signal }),
      ]);

      // Handle each result independently (partial failure handling)
      if (summaryResult.success) {
        setSummary(summaryResult.data);
      } else if (summaryResult.error.type !== 'network_error') {
        setErrors((prev) => ({ ...prev, summary: summaryResult.error.message }));
      }

      if (hourlyResult.success) {
        setHourlyData(hourlyResult.data.data);
      } else if (hourlyResult.error.type !== 'network_error') {
        setErrors((prev) => ({ ...prev, hourly: hourlyResult.error.message }));
      }

      if (outcomesResult.success) {
        setOutcomes(outcomesResult.data.outcomes);
      } else if (outcomesResult.error.type !== 'network_error') {
        setErrors((prev) => ({ ...prev, outcomes: outcomesResult.error.message }));
      }

      if (failuresResult.success) {
        setFailureReasons(failuresResult.data.reasons);
      } else if (failuresResult.error.type !== 'network_error') {
        setErrors((prev) => ({ ...prev, failures: failuresResult.error.message }));
      }

      // Update loading states
      setLoading({ summary: false, hourly: false, outcomes: false, failures: false });
    }

    fetchAllAnalytics();
    return () => controller.abort();
  }, [selectedDays]);

  // Transform hourly data for chart
  const chartData = useMemo(() => {
    return hourlyData.map((point) => ({
      hour: new Date(point.timestamp).toLocaleTimeString('en-US', {
        hour: '2-digit',
        hour12: true,
      }),
      queueDepth: point.queue_depth,
      processed: point.processed_count,
    }));
  }, [hourlyData]);

  // Transform outcomes for pie chart
  const pieData = useMemo(() => {
    return outcomes.map((o) => ({
      name: o.name.charAt(0).toUpperCase() + o.name.slice(1),
      value: o.count,
      color: OUTCOME_COLORS[o.name] || '#94a3b8',
    }));
  }, [outcomes]);

  // Computed values
  const avgWaitTimeMinutes = summary ? Math.round(summary.avg_wait_time_seconds / 60) : 0;

  return (
    <div className="space-y-6 md:space-y-8">
      {/* Header with Time Range Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <h2 className="text-2xl md:text-3xl font-bold text-slate-900 dark:text-white">
          Queue Analytics
        </h2>
        <div className="flex gap-2" role="group" aria-label="Select time period">
          {([7, 30, 90] as DaysPeriod[]).map((days) => (
            <button
              key={days}
              onClick={() => setSelectedDays(days)}
              aria-pressed={selectedDays === days}
              aria-label={`Show last ${days} days`}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none ${
                selectedDays === days
                  ? 'bg-purple-600 text-white shadow-md'
                  : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600'
              }`}
            >
              {days}d
            </button>
          ))}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Processed */}
        {loading.summary ? (
          <KPICardSkeleton />
        ) : (
          <article className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm" aria-labelledby="kpi-total-processed">
            <div className="flex justify-between items-start">
              <div className="p-2 bg-blue-50 dark:bg-blue-900/30 rounded-lg">
                <GitMerge className="w-6 h-6 text-blue-600 dark:text-blue-400" aria-hidden="true" />
              </div>
            </div>
            <h4 id="kpi-total-processed" className="text-slate-500 dark:text-slate-400 text-sm mt-4 font-medium">
              Total Processed
            </h4>
            <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1" aria-live="polite">
              {summary?.total_processed ?? '--'}
            </p>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
              Last {selectedDays} days
            </p>
          </article>
        )}

        {/* Avg Wait Time */}
        {loading.summary ? (
          <KPICardSkeleton />
        ) : (
          <article className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm" aria-labelledby="kpi-avg-wait">
            <div className="flex justify-between items-start">
              <div className="p-2 bg-orange-50 dark:bg-orange-900/30 rounded-lg">
                <Clock className="w-6 h-6 text-orange-600 dark:text-orange-400" aria-hidden="true" />
              </div>
            </div>
            <h4 id="kpi-avg-wait" className="text-slate-500 dark:text-slate-400 text-sm mt-4 font-medium">
              Avg. Wait Time
            </h4>
            <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1" aria-live="polite">
              {summary ? `${avgWaitTimeMinutes} min` : '--'}
            </p>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
              Time in queue before processing
            </p>
          </article>
        )}

        {/* Success Rate */}
        {loading.summary ? (
          <KPICardSkeleton />
        ) : (
          <article className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm" aria-labelledby="kpi-success-rate">
            <div className="flex justify-between items-start">
              <div className="p-2 bg-green-50 dark:bg-green-900/30 rounded-lg">
                <TrendingUp className="w-6 h-6 text-green-600 dark:text-green-400" aria-hidden="true" />
              </div>
            </div>
            <h4 id="kpi-success-rate" className="text-slate-500 dark:text-slate-400 text-sm mt-4 font-medium">
              Success Rate
            </h4>
            <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1" aria-live="polite">
              {summary ? `${summary.success_rate_percent.toFixed(1)}%` : '--'}
            </p>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
              MRs successfully merged
            </p>
          </article>
        )}

        {/* Daily Throughput */}
        {loading.summary ? (
          <KPICardSkeleton />
        ) : (
          <article className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm" aria-labelledby="kpi-throughput">
            <div className="flex justify-between items-start">
              <div className="p-2 bg-purple-50 dark:bg-purple-900/30 rounded-lg">
                <Activity className="w-6 h-6 text-purple-600 dark:text-purple-400" aria-hidden="true" />
              </div>
            </div>
            <h4 id="kpi-throughput" className="text-slate-500 dark:text-slate-400 text-sm mt-4 font-medium">
              Daily Throughput
            </h4>
            <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1" aria-live="polite">
              {summary ? `${summary.daily_throughput.toFixed(1)} MRs` : '--'}
            </p>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
              Average per day
            </p>
          </article>
        )}
      </div>

      {/* Main Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Queue Depth Chart */}
        {loading.hourly ? (
          <ChartSkeleton />
        ) : errors.hourly ? (
          <ErrorDisplay error={errors.hourly} title="Failed to load chart data" />
        ) : (
          <section className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm" aria-labelledby="chart-queue-depth">
            <h3 id="chart-queue-depth" className="text-lg font-semibold text-slate-900 dark:text-white mb-6">
              Queue Depth ({selectedDays === 7 ? '24h' : selectedDays === 30 ? '72h' : '168h'})
            </h3>
            <div className="h-64 w-full" role="img" aria-label={`Area chart showing queue depth over ${selectedDays === 7 ? '24 hours' : selectedDays === 30 ? '72 hours' : '168 hours'}`}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorQueue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8a2be2" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#8a2be2" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#e2e8f0"
                    strokeOpacity={0.4}
                    vertical={false}
                  />
                  <XAxis dataKey="hour" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                  <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(30, 41, 59, 0.9)',
                      borderColor: '#334155',
                      color: '#f8fafc',
                      borderRadius: '8px',
                    }}
                    itemStyle={{ color: '#e2e8f0' }}
                  />
                  <Area
                    type="monotone"
                    dataKey="queueDepth"
                    name="Queue Depth"
                    stroke="#8a2be2"
                    strokeWidth={3}
                    fillOpacity={1}
                    fill="url(#colorQueue)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

        {/* Processed Count Chart */}
        {loading.hourly ? (
          <ChartSkeleton />
        ) : errors.hourly ? (
          <ErrorDisplay error={errors.hourly} title="Failed to load chart data" />
        ) : (
          <section className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm" aria-labelledby="chart-processed">
            <h3 id="chart-processed" className="text-lg font-semibold text-slate-900 dark:text-white mb-6">
              MRs Processed per Hour
            </h3>
            <div className="h-64 w-full" role="img" aria-label="Bar chart showing merge requests processed per hour">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#e2e8f0"
                    strokeOpacity={0.4}
                    vertical={false}
                  />
                  <XAxis dataKey="hour" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                  <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(30, 41, 59, 0.9)',
                      borderColor: '#334155',
                      color: '#f8fafc',
                      borderRadius: '8px',
                    }}
                    cursor={{ fill: '#334155', opacity: 0.2 }}
                  />
                  <Legend />
                  <Bar
                    dataKey="processed"
                    name="Processed"
                    fill="#fc6d26"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}
      </div>

      {/* Breakdown Analysis */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Outcome Distribution */}
        {loading.outcomes ? (
          <ChartSkeleton />
        ) : errors.outcomes ? (
          <ErrorDisplay error={errors.outcomes} title="Failed to load outcome data" />
        ) : (
          <section className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm lg:col-span-1" aria-labelledby="chart-outcomes">
            <h3 id="chart-outcomes" className="text-lg font-semibold text-slate-900 dark:text-white mb-6">
              Outcome Distribution
            </h3>
            <div className="h-64 w-full flex justify-center" role="img" aria-label="Pie chart showing distribution of merge request outcomes: merged, failed, conflict, timeout">
              {pieData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color || COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'rgba(30, 41, 59, 0.9)',
                        borderColor: '#334155',
                        color: '#f8fafc',
                        borderRadius: '8px',
                      }}
                    />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-full text-slate-400">
                  No data available
                </div>
              )}
            </div>
          </section>
        )}

        {/* Failure Reasons */}
        {loading.failures ? (
          <ChartSkeleton className="lg:col-span-2" />
        ) : errors.failures ? (
          <ErrorDisplay error={errors.failures} title="Failed to load failure data" className="lg:col-span-2" />
        ) : (
          <section className="bg-white dark:bg-slate-800/50 p-6 rounded-2xl border border-slate-200 dark:border-slate-700/50 backdrop-blur-sm shadow-sm lg:col-span-2" aria-labelledby="chart-failures">
            <h3 id="chart-failures" className="text-lg font-semibold text-slate-900 dark:text-white mb-4">
              Failure Reasons
            </h3>
            <div className="space-y-4" role="list" aria-label="Failure reasons breakdown">
              {failureReasons.length > 0 ? (
                failureReasons.map((item, idx) => (
                  <div key={idx} className="flex items-center text-sm" role="listitem">
                    <div className="w-48 text-slate-600 dark:text-slate-400 truncate">
                      {item.reason}
                    </div>
                    <div
                      className="flex-1 h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden mx-4"
                      role="progressbar"
                      aria-valuenow={item.percentage}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={`${item.reason}: ${item.percentage.toFixed(0)}%`}
                    >
                      <div
                        className="h-full bg-red-500 rounded-full transition-all duration-300"
                        style={{ width: `${item.percentage}%` }}
                      />
                    </div>
                    <div className="w-16 text-right font-mono text-slate-700 dark:text-slate-300">
                      {item.count} ({item.percentage.toFixed(0)}%)
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-slate-400 text-center py-8" role="status">
                  No failures in the selected period
                </div>
              )}
            </div>
          </section>
        )}
      </div>
    </div>
  );
};

export default Analytics;
