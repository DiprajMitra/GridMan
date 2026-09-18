import { useQuery } from '@tanstack/react-query';
import { Activity, Wifi, WifiOff } from 'lucide-react';
import { checkHealth } from '../lib/api';

export default function HealthBadge() {
  const { data, isError, isLoading, dataUpdatedAt } = useQuery({
    queryKey: ['health'],
    queryFn: checkHealth,
    refetchInterval: 5000,
    retry: 1,
  });

  const isOnline = data?.status === 'ok';
  const lastCheck = dataUpdatedAt
    ? new Date(dataUpdatedAt).toLocaleTimeString()
    : '—';

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-100 dark:bg-surface-800 text-surface-500 text-sm">
        <Activity className="w-4 h-4 animate-pulse" />
        <span>Connecting…</span>
      </div>
    );
  }

  if (isError || !isOnline) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-50 dark:bg-red-950/40 text-red-600 dark:text-red-400 text-sm">
        <WifiOff className="w-4 h-4" />
        <span>Offline</span>
        <span className="text-xs opacity-60">{lastCheck}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-grid-50 dark:bg-grid-950/40 text-grid-700 dark:text-grid-400 text-sm">
      <Wifi className="w-4 h-4" />
      <span>Backend Online</span>
      <span className="hidden sm:inline text-xs opacity-60">{lastCheck}</span>
    </div>
  );
}
