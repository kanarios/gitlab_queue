import React from 'react';
import { RefreshCw } from 'lucide-react';
import { WebSocketState } from '../types';

interface ConnectionIndicatorProps {
  state: WebSocketState;
  onReconnect?: () => void;
  className?: string;
}

const statusConfig: Record<
  WebSocketState,
  { color: string; text: string; pulse: boolean }
> = {
  connecting: { color: 'bg-yellow-500', text: 'Connecting...', pulse: true },
  connected: { color: 'bg-green-500', text: 'Live', pulse: false },
  disconnected: { color: 'bg-slate-400', text: 'Disconnected', pulse: false },
  error: { color: 'bg-red-500', text: 'Connection Error', pulse: false },
};

/**
 * WebSocket connection status indicator with optional reconnect button.
 *
 * @param state - Current WebSocket connection state
 * @param onReconnect - Optional callback for reconnect button
 * @param className - Additional CSS classes
 */
const ConnectionIndicator: React.FC<ConnectionIndicatorProps> = ({
  state,
  onReconnect,
  className = '',
}) => {
  const config = statusConfig[state];

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <span
        className={`w-2 h-2 rounded-full ${config.color} ${config.pulse ? 'animate-pulse' : ''}`}
        aria-hidden="true"
      />
      <span className="text-sm text-slate-500 dark:text-slate-400">
        {config.text}
      </span>
      {(state === 'disconnected' || state === 'error') && onReconnect && (
        <button
          onClick={onReconnect}
          className="text-xs text-blue-600 dark:text-blue-400 hover:underline ml-2 flex items-center gap-1"
          aria-label="Reconnect to server"
        >
          <RefreshCw className="w-3 h-3" />
          Reconnect
        </button>
      )}
    </div>
  );
};

export default ConnectionIndicator;
