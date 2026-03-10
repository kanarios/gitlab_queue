/**
 * Centralized application configuration.
 *
 * All configuration values are loaded from environment variables with
 * sensible defaults. Use Vite's import.meta.env for build-time substitution.
 */

export const config = {
  // App branding
  appName: import.meta.env.VITE_APP_NAME || 'MergeBot',
  appVersion: import.meta.env.VITE_APP_VERSION || '1.0.0',

  // API URLs (used via Vite proxy in development)
  apiUrl: import.meta.env.VITE_API_URL || '',
  wsUrl: import.meta.env.VITE_WS_URL || '',

  // Health check interval in milliseconds
  healthCheckInterval: 30000, // 30 seconds
} as const;

/**
 * Build a GitLab MR URL from project web URL.
 */
export const getMrUrl = (projectWebUrl: string, iid: number): string =>
  `${projectWebUrl}/-/merge_requests/${iid}`;

/**
 * Build a GitLab pipeline URL from project web URL.
 */
export const getPipelineUrl = (projectWebUrl: string, pipelineId: number): string =>
  `${projectWebUrl}/-/pipelines/${pipelineId}`;

export type Config = typeof config;
