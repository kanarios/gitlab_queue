import type { MergeRequest, QueuePriority } from './types';

/** Prefer the server's effective priority, with compatibility for older snapshots. */
export function getQueuePriority(mr: Pick<MergeRequest, 'priority' | 'is_hotfix'>): QueuePriority {
  if (mr.priority === 'hotfix' || mr.priority === 'ordinary' || mr.priority === 'automated') {
    return mr.priority;
  }
  return mr.is_hotfix ? 'hotfix' : 'ordinary';
}

export const priorityNames: Record<QueuePriority, string> = {
  hotfix: 'Hotfix',
  ordinary: 'Ordinary',
  automated: 'Automated',
};

export const priorityDescriptions: Record<QueuePriority, string> = {
  hotfix: 'Runs before ordinary and automated waiting MRs. A running MR continues.',
  ordinary: 'Runs after hotfix and before automated waiting MRs. A running MR continues.',
  automated:
    'Matched an automation label configured for this project. Runs after hotfix and ordinary waiting MRs.',
};
