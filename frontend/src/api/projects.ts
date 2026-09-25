import { apiFetch } from './client';
import type { ApiResult, ProjectsResponse } from './types';

export async function getProjects(signal?: AbortSignal): Promise<ApiResult<ProjectsResponse>> {
  return apiFetch<ProjectsResponse>('/api/projects', { signal });
}
