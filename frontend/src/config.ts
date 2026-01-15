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

  // GitLab configuration
  gitlabUrl: import.meta.env.VITE_GITLAB_URL || 'https://gitlab.com',
  gitlabProjectPath: import.meta.env.VITE_GITLAB_PROJECT_PATH || '',

  // Health check interval in milliseconds
  healthCheckInterval: 30000, // 30 seconds
} as const;

/**
 * Build a GitLab MR URL from the configuration.
 */
export const getMrUrl = (iid: number): string => {
  const base = config.gitlabUrl.replace(/\/$/, '');
  const projectPath = config.gitlabProjectPath;
  if (!projectPath) {
    return `${base}/-/merge_requests/${iid}`;
  }
  return `${base}/${projectPath}/-/merge_requests/${iid}`;
};

/**
 * Build a GitLab pipeline URL from the configuration.
 */
export const getPipelineUrl = (pipelineId: number): string => {
  const base = config.gitlabUrl.replace(/\/$/, '');
  const projectPath = config.gitlabProjectPath;
  if (!projectPath) {
    return `${base}/-/pipelines/${pipelineId}`;
  }
  return `${base}/${projectPath}/-/pipelines/${pipelineId}`;
};

export type Config = typeof config;
