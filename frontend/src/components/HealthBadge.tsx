import { useQuery } from '@tanstack/react-query';
import { Activity, Wifi, WifiOff } from 'lucide-react';
import { checkHealth } from '../lib/api';

export default function HealthBadge() {
  const { data, isError, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ['health'],
    queryFn: checkHealth,
    refetchInterval: 10000,
    retry: 3,
    retryDelay: (attempt) => Math.min(2000 * 2 ** attempt, 15000),
  });

  const isOnline = data?.status === 'ok';
  const lastCheck = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString()
    : '—';

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-100 dark:bg-surface-800 text-surface-500 text-sm whitespace-nowrap">
        <Activity className="w-4 h-4 animate-pulse shrink-0" />
        <span>Connecting…</span>
      </div>
    );
  }

  if (isError || !isOnline) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 text-sm whitespace-nowrap">
        <WifiOff className="w-4 h-4 shrink-0" />
        <span>Offline</span>
        <span className="text-xs opacity-60 hidden sm:inline">{lastCheck}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-grid-50 dark:bg-grid-950/40 text-grid-700 dark:text-grid-400 text-sm whitespace-nowrap">
      <Wifi className="w-4 h-4 shrink-0" />
      <span>Backend Online</span>
      <span className="hidden sm:inline text-xs opacity-60">{lastCheck}</span>
    </div>
  );
}
