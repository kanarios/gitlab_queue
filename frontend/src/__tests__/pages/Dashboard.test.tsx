import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import Dashboard from '../../pages/Dashboard';
import { mockMergeRequest } from '../mocks/handlers';
import type { MergeRequest } from '../../types';

vi.mock('../../hooks/useProjectConfig', () => ({
  useProjectConfig: () => ({ projectWebUrl: 'https://gitlab.example.com/group/project' }),
}));

const request = (overrides: Partial<MergeRequest> & { position?: number }): MergeRequest => ({
  ...mockMergeRequest,
  status: 'queued' as const,
  is_hotfix: false,
  started_at: null,
  ...overrides,
});

const connected = {
  wsState: 'connected' as const,
  hasSnapshot: true,
  isSynchronized: true,
  onReconnect: vi.fn(),
};

beforeEach(() => {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    value: vi.fn((query: string) => ({
      matches: true,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

describe('Dashboard queue priorities', () => {
  it('waits for a snapshot, distinguishes queued-only from empty, and labels retained rows during reconnect', async () => {
    const onReconnect = vi.fn();
    const { rerender } = render(
      <Dashboard
        {...connected}
        queue={[]}
        hasSnapshot={false}
        isSynchronized={false}
        onReconnect={onReconnect}
      />
    );
    expect(screen.getByRole('heading', { name: 'Live Queue' })).toBeVisible();
    expect(screen.getByText('Syncing queue…')).toBeVisible();
    expect(screen.getByText('Loading queue…')).toBeVisible();
    expect(screen.queryByText('Queue is empty')).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Up Next (0)' })).not.toBeInTheDocument();

    const queue = [request({ mr_iid: 80, title: 'Waiting dependencies', priority: 'automated' })];
    rerender(<Dashboard {...connected} queue={queue} onReconnect={onReconnect} />);
    expect(screen.getByText('No MR is processing right now.')).toBeVisible();
    expect(screen.queryByText('Queue is empty')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Up Next (1)' })).toBeVisible();

    rerender(
      <Dashboard
        {...connected}
        queue={queue}
        wsState="disconnected"
        isSynchronized={false}
        onReconnect={onReconnect}
      />
    );
    expect(screen.getByText('Waiting dependencies')).toBeVisible();
    expect(screen.getByText('Updates paused. Showing the last received queue.')).toBeVisible();
    screen.getByRole('button', { name: 'Reconnect to server' }).click();
    expect(onReconnect).toHaveBeenCalledOnce();

    rerender(
      <Dashboard {...connected} queue={queue} wsState="connecting" isSynchronized={false} />
    );
    expect(screen.getByText('Waiting dependencies')).toBeVisible();
    expect(screen.queryByText('Loading queue…')).not.toBeInTheDocument();
    rerender(<Dashboard {...connected} queue={queue} isSynchronized={false} />);
    expect(screen.getByText('Syncing queue…')).toBeVisible();
    expect(screen.queryByText('Live', { exact: true })).not.toBeInTheDocument();

    await act(async () => {
      rerender(<Dashboard {...connected} queue={[]} />);
    });
    expect(screen.getByText('Queue is empty')).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Up Next (0)' })).toBeVisible();
    expect(
      screen.queryByText('Updates paused. Showing the last received queue.')
    ).not.toBeInTheDocument();
  });

  it.each([
    ['hotfix', false, 'Hotfix'],
    ['ordinary', true, 'Ordinary'],
    ['automated', true, 'Automated'],
    [undefined, true, 'Hotfix'],
    [undefined, false, 'Ordinary'],
    [null, true, 'Hotfix'],
    ['unknown', false, 'Ordinary'],
    ['unknown', true, 'Hotfix'],
  ])(
    'renders server priority %s / legacy hotfix %s consistently in both areas',
    (priority, isHotfix, expected) => {
      // Cast only at the wire boundary to exercise malformed and mixed-version payloads.
      const mr = {
        ...request({}),
        priority,
        is_hotfix: isHotfix,
        labels: ['hotfix', 'dependencies'],
        author: { name: 'Renovate', username: 'renovate', avatar_url: null },
      } as unknown as MergeRequest;
      render(
        <Dashboard
          {...connected}
          queue={[
            { ...mr, mr_iid: 91, title: 'Working', status: 'testing' },
            { ...mr, mr_iid: 92, title: 'Waiting' },
          ]}
        />
      );

      const active = screen.getByRole('region', { name: 'Processing now: Working' });
      const waiting = screen.getByRole('listitem', {
        name: `Waiting position 1: Waiting by Renovate, ${expected} priority`,
      });
      expect(active).toHaveAccessibleDescription(expect.stringContaining(`${expected} priority.`));
      for (const area of [active, waiting]) {
        expect(within(area).queryByText('Hotfix') !== null).toBe(expected === 'Hotfix');
        expect(within(area).queryByText('Automated') !== null).toBe(expected === 'Automated');
        expect(within(area).queryByText('Ordinary', { exact: true })).not.toBeInTheDocument();
      }
    }
  );

  it('reuses MR identity and focus when a new server snapshot relabels and reorders waiting rows', async () => {
    const user = userEvent.setup();
    vi.spyOn(Date, 'now').mockReturnValue(new Date('2026-10-18T10:00:00Z').getTime());
    const active = request({
      mr_iid: 90,
      title: 'Running',
      priority: 'automated',
      status: 'testing',
      started_at: '2026-10-18T09:58:55Z',
    });
    const hotfix = request({
      mr_iid: 100,
      title: 'Fix',
      priority: 'hotfix',
      queued_at: '2026-10-18T09:20:00Z',
    });
    const ordinary = request({
      mr_iid: 200,
      title: 'Feature',
      priority: 'ordinary',
      queued_at: '2026-10-18T09:30:00Z',
    });
    const automated = request({
      mr_iid: 10,
      title: 'Library',
      priority: 'automated',
      queued_at: '2026-10-18T09:00:00Z',
    });
    const { rerender } = render(
      <Dashboard {...connected} queue={[hotfix, ordinary, active, automated]} />
    );
    const activeNode = screen.getByRole('region', { name: 'Processing now: Running' });
    const link = screen.getByRole('link', {
      name: 'Open merge request !10 in GitLab (opens in new tab)',
    });
    await user.tab();
    await user.tab();
    await user.tab();
    await user.tab();
    await user.tab();
    await user.tab();
    expect(link).toHaveFocus();

    await act(async () => {
      // Deliberately use an order that a client comparator might "correct".
      rerender(
        <Dashboard
          {...connected}
          queue={[
            { ...automated, priority: 'ordinary', labels: ['merge_queue'] },
            hotfix,
            { ...active, priority: 'hotfix' },
            ordinary,
          ]}
        />
      );
    });

    const rows = within(screen.getByRole('list', { name: 'Pending merge requests' })).getAllByRole(
      'listitem'
    );
    expect(rows.map((row) => within(row).getByRole('link').textContent)).toEqual([
      '!10',
      '!100',
      '!200',
    ]);
    expect(rows[0]).toHaveAccessibleName(
      'Waiting position 1: Library by Test User, Ordinary priority'
    );
    expect(within(rows[0]).queryByText('Automated')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Up Next (3)' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Processing now: Running' })).toBe(activeNode);
    expect(within(activeNode).getByText('Hotfix')).toBeVisible();
    expect(within(activeNode).getByText('Testing')).toBeVisible();
    expect(within(activeNode).getByText('01:05')).toBeVisible();
    expect(
      screen.getByRole('link', { name: 'Open merge request !10 in GitLab (opens in new tab)' })
    ).toBe(link);
    expect(link).toHaveFocus();
  });

  it('shows an unavailable queue before the first snapshot and a last-known empty queue after disconnect', () => {
    const { rerender } = render(
      <Dashboard
        {...connected}
        queue={[]}
        hasSnapshot={false}
        isSynchronized={false}
        wsState="error"
      />
    );
    expect(screen.getByText('Queue unavailable')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Reconnect to server' })).toBeVisible();
    expect(screen.queryByText('Queue is empty')).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Up Next (0)' })).not.toBeInTheDocument();
    rerender(<Dashboard {...connected} queue={[]} wsState="disconnected" isSynchronized={false} />);
    expect(screen.getByText('Queue is empty')).toBeVisible();
    expect(screen.getByText('Updates paused. Showing the last received queue.')).toBeVisible();
  });

  it('shows zero waiting items alongside an active MR', () => {
    render(
      <Dashboard
        {...connected}
        queue={[request({ mr_iid: 1, title: 'Active only', status: 'rebasing' })]}
      />
    );
    expect(screen.getByRole('region', { name: 'Processing now: Active only' })).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Up Next (0)' })).toBeVisible();
    expect(screen.getByText('No other items in queue.')).toBeVisible();
    expect(screen.queryByText('Queue is empty')).not.toBeInTheDocument();
  });

  it('keeps the running automated MR separate and numbers waiting MRs in server order', () => {
    const queue = [
      request({
        mr_iid: 102,
        title: 'Fix timeout',
        priority: 'hotfix',
        labels: ['hotfix', 'dependencies'],
        position: 1,
      }),
      request({
        mr_iid: 101,
        title: 'Add export',
        priority: 'ordinary',
        author: { name: 'Renovate', username: 'renovate', avatar_url: null },
        position: 2,
      }),
      request({
        mr_iid: 90,
        title: 'Running dependencies',
        priority: 'automated',
        status: 'testing',
        started_at: new Date(Date.now() - 65_000).toISOString(),
        position: 3,
      }),
      request({
        mr_iid: 80,
        title: 'Update library',
        priority: 'automated',
        author: { name: 'Alice', username: 'alice', avatar_url: null },
        position: 4,
      }),
    ];

    render(<Dashboard {...connected} queue={queue} />);

    const active = screen.getByRole('region', { name: 'Processing now: Running dependencies' });
    expect(within(active).getByText('Automated')).toBeVisible();
    expect(within(active).getByText('Testing')).toBeVisible();
    expect(within(active).getByText('01:05')).toBeVisible();
    expect(screen.getByText('The running MR continues before waiting MRs start.')).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Up Next (3)' })).toBeVisible();

    const waiting = screen.getByRole('list', { name: 'Pending merge requests' });
    const rows = within(waiting).getAllByRole('listitem');
    expect(rows.map((row) => row.getAttribute('aria-label'))).toEqual([
      'Waiting position 1: Fix timeout by Test User, Hotfix priority',
      'Waiting position 2: Add export by Renovate, Ordinary priority',
      'Waiting position 3: Update library by Alice, Automated priority',
    ]);
    expect(within(rows[0]).getByText('Hotfix')).toBeVisible();
    expect(within(rows[0]).queryByText('Automated')).not.toBeInTheDocument();
    expect(within(rows[1]).queryByText('Hotfix')).not.toBeInTheDocument();
    expect(within(rows[1]).queryByText('Automated')).not.toBeInTheDocument();
    expect(within(rows[2]).getByText('Automated')).toBeVisible();
    expect(within(rows[0]).getByText('#1')).toBeVisible();
    expect(within(rows[2]).getByText('#3')).toBeVisible();
    expect(within(waiting).queryByText('Running dependencies')).not.toBeInTheDocument();
  });
});
