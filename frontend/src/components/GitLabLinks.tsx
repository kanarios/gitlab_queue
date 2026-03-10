import React from 'react';
import { ExternalLink } from 'lucide-react';
import { getMrUrl, getPipelineUrl } from '../config';

interface GitLabMrLinkProps {
  projectWebUrl: string | null;
  iid: number;
  className?: string;
  showIcon?: boolean;
}

export const GitLabMrLink: React.FC<GitLabMrLinkProps> = ({
  projectWebUrl,
  iid,
  className = 'font-mono text-blue-600 dark:text-blue-400',
  showIcon = false,
}) => {
  if (!projectWebUrl) {
    return <span className={className}>!{iid}</span>;
  }

  return (
    <a
      href={getMrUrl(projectWebUrl, iid)}
      target="_blank"
      rel="noopener noreferrer"
      className={`${className} hover:underline flex items-center group focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none rounded`}
      aria-label={`Open merge request !${iid} in GitLab (opens in new tab)`}
    >
      !{iid}
      {showIcon && (
        <ExternalLink className="w-3 h-3 ml-1 opacity-0 group-hover:opacity-100 transition-opacity" aria-hidden="true" />
      )}
    </a>
  );
};

interface GitLabPipelineLinkProps {
  projectWebUrl: string | null;
  pipelineId: number;
  className?: string;
}

export const GitLabPipelineLink: React.FC<GitLabPipelineLinkProps> = ({
  projectWebUrl,
  pipelineId,
  className = 'font-mono text-slate-600 dark:text-slate-300',
}) => {
  if (!projectWebUrl) {
    return <span className={className}>#{pipelineId}</span>;
  }

  return (
    <a
      href={getPipelineUrl(projectWebUrl, pipelineId)}
      target="_blank"
      rel="noopener noreferrer"
      className={`flex items-center ${className} hover:text-blue-600 dark:hover:text-blue-400 transition-colors focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none rounded`}
      aria-label={`View pipeline #${pipelineId} in GitLab (opens in new tab)`}
    >
      <span className="font-mono mr-1">#{pipelineId}</span>
      <ExternalLink className="w-3 h-3 opacity-50" aria-hidden="true" />
    </a>
  );
};
