import { apiFetch } from './client';
import type { ApiResult } from './types';

interface ProjectConfig {
  project_web_url: string;
}

export async function getProjectConfig(
  projectId: number,
  signal?: AbortSignal
): Promise<ApiResult<ProjectConfig>> {
  return apiFetch<ProjectConfig>(`/api/projects/${projectId}/config`, { signal });
}
