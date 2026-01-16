import React from 'react';

interface SkeletonProps {
  className?: string;
}

/**
 * Base skeleton component with pulse animation.
 */
export const Skeleton: React.FC<SkeletonProps> = ({ className = '' }) => (
  <div className={`animate-pulse bg-slate-200 dark:bg-slate-700 rounded ${className}`} />
);

/**
 * Dashboard header skeleton.
 */
export const DashboardHeaderSkeleton: React.FC = () => (
  <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
    <div>
      <Skeleton className="h-8 w-32 mb-2" />
      <Skeleton className="h-4 w-48" />
    </div>
    <Skeleton className="h-6 w-24" />
  </div>
);

/**
 * Active MR card skeleton for Dashboard.
 */
export const ActiveMRSkeleton: React.FC = () => (
  <div className="bg-white dark:bg-slate-800/50 rounded-2xl border border-slate-200 dark:border-slate-700 p-5 md:p-8 animate-pulse">
    <div className="flex items-start gap-4 mb-8">
      <Skeleton className="w-14 h-14 md:w-16 md:h-16 rounded-xl" />
      <div className="flex-1 space-y-3">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-7 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    </div>
    <Skeleton className="h-2 w-full rounded-full" />
    <div className="flex justify-between mt-4">
      {[1, 2, 3, 4].map((i) => (
        <Skeleton key={i} className="h-4 w-16" />
      ))}
    </div>
  </div>
);

/**
 * Queue item skeleton for Dashboard "Up Next" list.
 */
export const QueueItemSkeleton: React.FC = () => (
  <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-4 animate-pulse">
    <div className="flex items-center gap-4">
      <Skeleton className="w-6 h-6 rounded" />
      <Skeleton className="w-10 h-10 rounded-full" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-5 w-2/3" />
        <Skeleton className="h-4 w-1/3" />
      </div>
    </div>
  </div>
);

/**
 * Full dashboard loading skeleton (header + active MR + queue).
 */
export const DashboardSkeleton: React.FC = () => (
  <div className="space-y-6 md:space-y-8">
    <DashboardHeaderSkeleton />
    <ActiveMRSkeleton />
    <div>
      <Skeleton className="h-6 w-32 mb-4" />
      <div className="space-y-3">
        <QueueItemSkeleton />
        <QueueItemSkeleton />
      </div>
    </div>
  </div>
);

/**
 * Table row skeleton for History page.
 */
export const TableRowSkeleton: React.FC = () => (
  <div className="flex items-center space-x-4 py-4 px-6">
    <Skeleton className="h-4 w-16" />
    <Skeleton className="h-4 w-20" />
    <Skeleton className="h-4 flex-1" />
    <Skeleton className="h-4 w-24" />
  </div>
);

/**
 * History table skeleton with multiple rows.
 */
export const HistoryTableSkeleton: React.FC<{ rows?: number }> = ({ rows = 5 }) => (
  <div className="animate-pulse p-6 space-y-4">
    {[...Array(rows)].map((_, i) => (
      <div key={i} className="flex items-center space-x-4">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 flex-1" />
        <Skeleton className="h-4 w-24" />
      </div>
    ))}
  </div>
);

/**
 * KPI card skeleton for Analytics.
 */
export const KPICardSkeleton: React.FC = () => (
  <Skeleton className="h-32 rounded-2xl" />
);

/**
 * Chart skeleton for Analytics.
 */
export const ChartSkeleton: React.FC<{ className?: string }> = ({ className = '' }) => (
  <Skeleton className={`h-80 rounded-2xl ${className}`} />
);

/**
 * Analytics page skeleton with KPI cards and charts.
 */
export const AnalyticsSkeleton: React.FC = () => (
  <div className="space-y-6 md:space-y-8">
    {/* KPI Cards */}
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      <KPICardSkeleton />
      <KPICardSkeleton />
      <KPICardSkeleton />
      <KPICardSkeleton />
    </div>
    {/* Charts */}
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      <ChartSkeleton />
      <ChartSkeleton />
    </div>
    {/* Bottom row */}
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <ChartSkeleton />
      <ChartSkeleton className="lg:col-span-2" />
    </div>
  </div>
);

// Default export for backward compatibility
export default Skeleton;
