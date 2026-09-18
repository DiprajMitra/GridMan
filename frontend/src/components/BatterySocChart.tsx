import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';
import type { HourlyPlan } from '../types/energy';
import { BatteryCharging } from 'lucide-react';

interface BatterySocChartProps {
  plan: HourlyPlan[];
  minimumEnergy: number;
  capacity: number;
}

export default function BatterySocChart({
  plan,
  minimumEnergy,
  capacity,
}: BatterySocChartProps) {
  if (!plan.length) {
    return (
      <div className="card">
        <div className="card-header">
          <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 flex items-center gap-2">
            <BatteryCharging className="w-4 h-4 text-chart-battery" />
            Battery State of Charge
          </h3>
        </div>
        <div className="card-body flex items-center justify-center h-48">
          <p className="text-sm text-surface-400">
            Run optimization to view SoC trajectory
          </p>
        </div>
      </div>
    );
  }

  const chartData = plan.map((p) => ({
    hour: `${p.hour}:00`,
    SoC: p.battery_energy_after_kwh,
    action: p.battery_action,
  }));

  const socGradientId = 'socGradient';

  return (
    <div className="card">
      <div className="card-header">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 flex items-center gap-2">
            <BatteryCharging className="w-4 h-4 text-chart-battery" />
            Battery State of Charge
          </h3>
          <div className="flex gap-3 text-[10px] text-surface-400">
            <span className="flex items-center gap-1">
              <span className="w-6 h-0.5 bg-red-400 rounded" />
              Min Reserve
            </span>
            <span className="flex items-center gap-1">
              <span className="w-6 h-0.5 bg-surface-400 rounded" style={{ opacity: 0.4 }} />
              Capacity
            </span>
          </div>
        </div>
      </div>
      <div className="card-body">
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={chartData} margin={{ top: 8, right: 12, left: 8, bottom: 8 }}>
            <defs>
              <linearGradient id={socGradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-chart-battery)" stopOpacity={0.3} />
                <stop offset="95%" stopColor="var(--color-chart-battery)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--color-surface-200)"
              opacity={0.5}
            />
            <XAxis
              dataKey="hour"
              tick={{ fontSize: 10, fill: 'var(--color-surface-400)' }}
              interval={2}
            />
            <YAxis
              domain={[0, capacity]}
              tick={{ fontSize: 10, fill: 'var(--color-surface-400)' }}
              width={48}
              label={{
                value: 'kWh',
                angle: -90,
                position: 'insideTopLeft',
                offset: 14,
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
              formatter={(value) => [`${value} kWh`, 'Battery SoC']}
            />
            {/* Minimum reserve reference line */}
            <ReferenceLine
              y={minimumEnergy}
              stroke="#f87171"
              strokeDasharray="6 3"
              strokeWidth={1.5}
              label={{
                value: `Min: ${minimumEnergy} kWh`,
                position: 'right',
                style: { fontSize: 9, fill: '#f87171' },
              }}
            />
            {/* Capacity reference line */}
            <ReferenceLine
              y={capacity}
              stroke="var(--color-surface-400)"
              strokeDasharray="2 4"
              strokeWidth={1}
              opacity={0.4}
            />
            <Area
              type="monotone"
              dataKey="SoC"
              stroke="var(--color-chart-battery)"
              strokeWidth={2}
              fill={`url(#${socGradientId})`}
              dot={{ r: 2.5, fill: 'var(--color-chart-battery)', strokeWidth: 0 }}
              activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--color-surface-900)' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
