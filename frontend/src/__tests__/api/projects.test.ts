import { beforeEach, describe, expect, it } from 'vitest';
import { setToken } from '../../auth/storage';
import { getProjects } from '../../api/projects';

describe('api/projects', () => {
  beforeEach(() => {
    localStorage.clear();
    setToken('test-token');
  });

  it('loads the accessible project list', async () => {
    const result = await getProjects();

    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.projects).toEqual([
        {
          project_id: 1,
          web_url: 'https://gitlab.example.com/group/project',
          name: 'group/project',
        },
        {
          project_id: 2,
          web_url: 'https://gitlab.example.com/group/second',
          name: 'group/second',
        },
      ]);
    }
  });

  it('supports cancellation while loading projects', async () => {
    const controller = new AbortController();
    controller.abort();

    const result = await getProjects(controller.signal);

    expect(result.success).toBe(false);
    if (!result.success) expect(result.error.type).toBe('network_error');
  });
});
