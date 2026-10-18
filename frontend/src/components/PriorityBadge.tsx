import { useId } from 'react';
import { ArrowDown, Flame } from 'lucide-react';
import type { QueuePriority } from '../types';
import { priorityDescriptions, priorityNames } from '../queuePriority';

interface PriorityBadgeProps {
  priority: QueuePriority;
  descriptionId?: string;
}

export default function PriorityBadge({ priority, descriptionId }: PriorityBadgeProps) {
  const generatedId = useId();
  const id = descriptionId ?? generatedId;
  const name = priorityNames[priority];
  const description = priorityDescriptions[priority];

  return (
    <>
      <span id={id} className="sr-only">
        {name} priority. {description}
      </span>
      {priority !== 'ordinary' && (
        <span
          className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold ${
            priority === 'hotfix'
              ? 'border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-500/30 dark:bg-orange-500/10 dark:text-orange-300'
              : 'border-slate-200 bg-slate-100 text-slate-700 dark:border-slate-600 dark:bg-slate-700/50 dark:text-slate-200'
          }`}
          aria-label={`${name} priority`}
          aria-describedby={id}
          title={description}
        >
          {priority === 'hotfix' ? (
            <Flame className="h-3 w-3" aria-hidden="true" />
          ) : (
            <ArrowDown className="h-3 w-3" aria-hidden="true" />
          )}
          {name}
        </span>
      )}
    </>
  );
}
