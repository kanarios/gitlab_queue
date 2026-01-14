export type MRStatus =
  | 'queued'
  | 'rebasing'
  | 'testing'
  | 'merging'
  | 'merged'
  | 'failed'
  | 'conflict'
  | 'timeout'
  | 'removed';

export interface Author {
  name: string;
  username: string;
  avatar_url: string | null;
}

export interface PipelineInfo {
  id: number;
  status: string | null;
}

export interface MergeRequest {
  mr_iid: number;
  title: string;
  author: Author;
  status: MRStatus;
  labels: string[];
  is_hotfix: boolean;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  target_branch: string;
  pipeline: PipelineInfo | null;
  failure_reason: string | null;
}

export interface QueueStats {
  total_processed: number;
  avg_wait_time_seconds: number;
  success_rate_percent: number;
}

/**
 * Queue statistics from WebSocket (different structure from REST API).
 * Counts MRs by current processing state.
 */
export interface QueueStatsFromWS {
  queued: number;
  rebasing: number;
  testing: number;
  merging: number;
}

export type ViewMode = 'dashboard' | 'history' | 'analytics';

/**
 * WebSocket connection state for UI display.
 */
export type WebSocketState = 'connecting' | 'connected' | 'disconnected' | 'error';

/**
 * WebSocket events from backend.
 * Note: Backend uses camelCase for field names (oldStatus, newStatus, finishedAt, failureReason).
 */
export type WSEvent =
  | { type: 'queue:updated'; data: { queue: MergeRequest[]; stats: QueueStatsFromWS } }
  | { type: 'mr:status_changed'; data: { iid: number; oldStatus: string; newStatus: string } }
  | { type: 'mr:completed'; data: { iid: number; status: string; finishedAt: string; failureReason: string | null } };

export function isQueueUpdatedEvent(
  event: WSEvent
): event is Extract<WSEvent, { type: 'queue:updated' }> {
  return event.type === 'queue:updated';
}

export function isMrStatusChangedEvent(
  event: WSEvent
): event is Extract<WSEvent, { type: 'mr:status_changed' }> {
  return event.type === 'mr:status_changed';
}

export function isMrCompletedEvent(
  event: WSEvent
): event is Extract<WSEvent, { type: 'mr:completed' }> {
  return event.type === 'mr:completed';
}

// Auth Types
export interface User {
  id: number;
  username: string;
  name: string;
  email: string | null;
  avatar_url: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: 'bearer';
  user: User;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export type AuthErrorType =
  | 'access_denied'
  | 'invalid_state'
  | 'network_error'
  | 'token_expired'
  | 'server_error'
  | 'no_access';

export interface AuthError {
  type: AuthErrorType;
  message: string;
}
