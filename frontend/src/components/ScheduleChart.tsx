import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import type { HourlyPlan, HourlyProfile } from '../types/energy';
import { BarChart3 } from 'lucide-react';

interface ScheduleChartProps {
  plan: HourlyPlan[];
  inputHours?: HourlyProfile[];
}

export default function ScheduleChart({ plan, inputHours }: ScheduleChartProps) {
  if (!plan.length) {
    return (
      <div className="card">
        <div className="card-header">
          <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-chart-grid" />
            24-Hour Energy Dispatch
          </h3>
        </div>
        <div className="card-body flex items-center justify-center h-64">
          <p className="text-sm text-surface-400">
            Run optimization to view the dispatch schedule
          </p>
        </div>
      </div>
    );
  }

  const chartData = plan.map((p) => {
    const demand = inputHours?.find((h) => h.hour === p.hour)?.demand_kwh ?? 0;
    return {
      hour: `${p.hour}:00`,
      hourNum: p.hour,
      'Grid Import': p.grid_kwh,
      'Solar Used': p.solar_used_kwh,
      'Battery Charge': p.battery_action === 'charge' ? p.battery_kwh : 0,
      'Battery Discharge': p.battery_action === 'discharge' ? p.battery_kwh : 0,
      'Campus Demand': demand,
    };
  });

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-chart-grid" />
          24-Hour Energy Dispatch
        </h3>
      </div>
      <div className="card-body">
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={chartData} margin={{ top: 8, right: 12, left: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-surface-200)" opacity={0.5} />
            <XAxis
              dataKey="hour"
              tick={{ fontSize: 10, fill: 'var(--color-surface-400)' }}
              interval={2}
            />
            <YAxis
              tick={{ fontSize: 10, fill: 'var(--color-surface-400)' }}
              width={48}
              label={{
                value: 'kWh',
                angle: -90,
                position: 'insideTopLeft',
                offset: 18,
                style: { fontSize: 10, fill: 'var(--color-surface-400)', textAnchor: 'middle' },
              }}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--color-surface-900)',
                border: '1px solid var(--color-surface-700)',
                borderRadius: '8px',
                fontSize: '12px',
                color: 'var(--color-surface-100)',
              }}
              wrapperStyle={{ outline: 'none' }}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px', paddingTop: '8px' }}
            />
            <ReferenceLine y={0} stroke="var(--color-surface-300)" />
            <Bar
              dataKey="Grid Import"
              stackId="supply"
              fill="var(--color-chart-grid)"
              radius={[0, 0, 0, 0]}
            />
            <Bar
              dataKey="Solar Used"
              stackId="supply"
              fill="var(--color-chart-solar)"
              radius={[0, 0, 0, 0]}
            />
            <Bar
              dataKey="Battery Discharge"
              stackId="supply"
              fill="var(--color-chart-discharge)"
              radius={[2, 2, 0, 0]}
            />
            <Bar
              dataKey="Battery Charge"
              fill="var(--color-chart-charge)"
              radius={[2, 2, 0, 0]}
              opacity={0.7}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
