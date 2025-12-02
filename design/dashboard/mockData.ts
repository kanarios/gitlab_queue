import { MergeRequest, MRStatus } from './types';

const avatars = [
  "https://picsum.photos/seed/user1/64/64",
  "https://picsum.photos/seed/user2/64/64",
  "https://picsum.photos/seed/user3/64/64",
  "https://picsum.photos/seed/user4/64/64",
  "https://picsum.photos/seed/user5/64/64",
];

export const initialQueue: MergeRequest[] = [
  {
    iid: 1042,
    title: "feat: Implement new authentication flow",
    author: { name: "Alice Dev", username: "@alice", avatar: avatars[0] },
    status: MRStatus.REBASING,
    labels: ["merge_queue", "feature"],
    isHotfix: false,
    queuedAt: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
    startedAt: new Date(Date.now() - 1000 * 30).toISOString(),
    targetBranch: "master",
  },
  {
    iid: 1045,
    title: "fix: Critical security patch for payment gateway",
    author: { name: "Bob Ops", username: "@bob", avatar: avatars[1] },
    status: MRStatus.QUEUED,
    labels: ["merge_queue", "hotfix", "security"],
    isHotfix: true,
    queuedAt: new Date(Date.now() - 1000 * 60 * 2).toISOString(),
    targetBranch: "master",
  },
  {
    iid: 1049,
    title: "chore: Update dependencies",
    author: { name: "Charlie Bot", username: "@charlie", avatar: avatars[2] },
    status: MRStatus.QUEUED,
    labels: ["merge_queue", "maintenance"],
    isHotfix: false,
    queuedAt: new Date(Date.now() - 1000 * 60 * 10).toISOString(),
    targetBranch: "master",
  },
  {
    iid: 1051,
    title: "feat: Add dark mode support",
    author: { name: "Dana UI", username: "@dana", avatar: avatars[3] },
    status: MRStatus.QUEUED,
    labels: ["merge_queue", "ui"],
    isHotfix: false,
    queuedAt: new Date(Date.now() - 1000 * 60 * 1).toISOString(),
    targetBranch: "master",
  }
];

export const initialHistory: MergeRequest[] = [
  {
    iid: 1038,
    title: "fix: Typo in readme",
    author: { name: "Alice Dev", username: "@alice", avatar: avatars[0] },
    status: MRStatus.MERGED,
    labels: ["merge_queue"],
    isHotfix: false,
    queuedAt: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
    finishedAt: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
    targetBranch: "master",
    pipeline: { id: 5543, status: 'success', jobs_failed: [], duration_seconds: 320 }
  },
  {
    iid: 1039,
    title: "feat: Large refactor of core module",
    author: { name: "Bob Ops", username: "@bob", avatar: avatars[1] },
    status: MRStatus.CONFLICT,
    labels: ["merge_queue", "refactor"],
    isHotfix: false,
    queuedAt: new Date(Date.now() - 1000 * 60 * 90).toISOString(),
    finishedAt: new Date(Date.now() - 1000 * 60 * 85).toISOString(),
    targetBranch: "master",
    failureReason: "Merge conflict in src/core/processor.py"
  },
  {
    iid: 1040,
    title: "fix: Memory leak in worker",
    author: { name: "Eve Perf", username: "@eve", avatar: avatars[4] },
    status: MRStatus.FAILED,
    labels: ["merge_queue", "bug"],
    isHotfix: false,
    queuedAt: new Date(Date.now() - 1000 * 60 * 120).toISOString(),
    finishedAt: new Date(Date.now() - 1000 * 60 * 100).toISOString(),
    targetBranch: "master",
    pipeline: { id: 5540, status: 'failed', jobs_failed: ['test_concurrent', 'build_worker_image'], duration_seconds: 400 },
    failureReason: "Pipeline failed after 1 retry"
  }
];

export const generateAnalyticsData = () => {
  const data = [];
  for (let i = 0; i < 24; i++) {
    data.push({
      hour: `${i}:00`,
      queueDepth: Math.floor(Math.random() * 8),
      avgMergeTime: Math.floor(Math.random() * 20) + 5,
      successRate: Math.floor(Math.random() * 20) + 80,
    });
  }
  return data;
};