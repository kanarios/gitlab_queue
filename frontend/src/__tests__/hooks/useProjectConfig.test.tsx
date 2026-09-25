import { describe, expect, it, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { ProjectProvider } from '../../projects/ProjectContext';
import { useProjectConfig } from '../../hooks/useProjectConfig';

function wrapper({ children }: { children: ReactNode }) {
  return <ProjectProvider>{children}</ProjectProvider>;
}

describe('hooks/useProjectConfig', () => {
  beforeEach(() => localStorage.clear());

  it('returns the selected project web URL from the project list', async () => {
    const { result } = renderHook(() => useProjectConfig(), { wrapper });

    await waitFor(() => {
      expect(result.current.projectWebUrl).toBe(
        'https://gitlab.example.com/group/project'
      );
    });
  });
});
