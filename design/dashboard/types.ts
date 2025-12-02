export enum MRStatus {
  QUEUED = 'queued',
  REBASING = 'rebasing',
  TESTING = 'testing',
  MERGING = 'merging',
  MERGED = 'merged',
  FAILED = 'failed',
  CONFLICT = 'conflict',
  TIMEOUT = 'timeout',
  REMOVED = 'removed'
}

export interface Author {
  name: string;
  avatar: string;
  username: string;
}

export interface PipelineStats {
  id: number;
  status: 'running' | 'success' | 'failed' | 'canceled';
  jobs_failed: string[];
  duration_seconds: number;
}

export interface MergeRequest {
  iid: number;
  title: string;
  author: Author;
  status: MRStatus;
  labels: string[];
  isHotfix: boolean;
  queuedAt: string; // ISO String
  startedAt?: string;
  finishedAt?: string;
  targetBranch: string;
  pipeline?: PipelineStats;
  failureReason?: string;
}

export interface QueueStats {
  totalProcessed: number;
  avgWaitTimeMinutes: number;
  successRate: number;
  activeSince: string;
}

export type ViewMode = 'dashboard' | 'history' | 'analytics';
