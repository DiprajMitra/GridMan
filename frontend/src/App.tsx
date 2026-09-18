import { useState, useCallback, useRef } from 'react';
import { useMutation } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import {
  Sun,
  Moon,
  Zap,
  Play,
  Loader2,
  Settings,
  ChevronDown,
  Server,
  FileText,
} from 'lucide-react';

import type {
  OptimizationRequest,
  OptimizationResponse,
  BatteryConfig,
  HourlyProfile,
} from './types/energy';
import { optimizeEnergy, setBaseURL, getBaseURL } from './lib/api';
import { SCENARIO_PRESETS, getPresetById } from './lib/presets';

import HealthBadge from './components/HealthBadge';
import OperatorNotesInput from './components/OperatorNotesInput';
import BatterySettingsCard from './components/BatterySettingsCard';
import HourlyProfileTable from './components/HourlyProfileTable';
import DirectiveInspector from './components/DirectiveInspector';
import SummaryCards from './components/SummaryCards';
import ScheduleChart from './components/ScheduleChart';
import BatterySocChart from './components/BatterySocChart';
import DispatchTable from './components/DispatchTable';

export default function App() {
  // ─── Theme ───
  const [isDark, setIsDark] = useState(true);
  const toggleTheme = useCallback(() => {
    setIsDark((prev) => {
      const next = !prev;
      document.documentElement.classList.toggle('dark', next);
      return next;
    });
  }, []);

  // ─── Backend URL ───
  const [backendUrl, setBackendUrl] = useState(getBaseURL());
  const [showUrlInput, setShowUrlInput] = useState(false);

  const applyUrl = () => {
    setBaseURL(backendUrl);
    toast.success(`Backend URL updated to ${backendUrl}`);
    setShowUrlInput(false);
  };

  // ─── Scenario State ───
  const defaultPreset = SCENARIO_PRESETS[0];
  const [selectedPresetId, setSelectedPresetId] = useState(defaultPreset.id);
  const [scenarioId, setScenarioId] = useState(defaultPreset.data.scenario_id);
  const [operatorNotes, setOperatorNotes] = useState<string[]>([
    ...defaultPreset.data.operator_notes,
  ]);
  const [battery, setBattery] = useState<BatteryConfig>({
    ...defaultPreset.data.battery,
  });
  const [hours, setHours] = useState<HourlyProfile[]>([
    ...defaultPreset.data.hours,
  ]);

  // ─── Results ───
  const [result, setResult] = useState<OptimizationResponse | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const timerRef = useRef<number>(0);

  // ─── Preset Selector ───
  const loadPreset = (presetId: string) => {
    const preset = getPresetById(presetId);
    if (!preset) return;
    setSelectedPresetId(presetId);
    setScenarioId(preset.data.scenario_id);
    setOperatorNotes([...preset.data.operator_notes]);
    setBattery({ ...preset.data.battery });
    setHours([...preset.data.hours]);
    setResult(null);
    setLatencyMs(null);
  };

  // ─── Mutation ───
  const mutation = useMutation({
    mutationFn: optimizeEnergy,
    onMutate: () => {
      timerRef.current = Date.now();
    },
    onSuccess: (data) => {
      setResult(data);
      setLatencyMs(Date.now() - timerRef.current);
      toast.success('Optimization complete!');
    },
    onError: (error: Error & { response?: { status?: number; data?: { detail?: string } } }) => {
      setLatencyMs(Date.now() - timerRef.current);
      const status = error.response?.status;
      const detail = error.response?.data?.detail;

      if (status === 422 || status === 400) {
        toast.error(`Validation Error (${status}): ${detail || 'Invalid input'}`);
      } else if (error.message?.includes('timeout')) {
        toast.error('Request timed out (>30s). The backend may be overloaded.');
      } else {
        toast.error(`Network Error: ${error.message}`);
      }
    },
  });

  const handleOptimize = () => {
    const request: OptimizationRequest = {
      scenario_id: scenarioId,
      operator_notes: operatorNotes.filter((n) => n.trim() !== ''),
      hours,
      battery,
    };
    mutation.mutate(request);
  };

  return (
    <div className="min-h-screen flex flex-col">
      {/* ════════════════ TOP BAR ════════════════ */}
      <header className="sticky top-0 z-50 border-b border-surface-200 dark:border-surface-800 bg-white/80 dark:bg-surface-950/80 backdrop-blur-xl">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
          {/* Logo */}
          <div className="flex items-center gap-2.5 shrink-0">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-grid-500 to-grid-700 flex items-center justify-center">
              <Zap className="w-4.5 h-4.5 text-white" />
            </div>
            <div>
              <h1 className="text-sm font-bold text-surface-900 dark:text-surface-100 leading-tight">
                GridWise
              </h1>
              <p className="text-[10px] text-surface-400 leading-tight hidden sm:block">
                Smart Campus Energy Optimizer
              </p>
            </div>
          </div>

          {/* Center controls */}
          <div className="flex items-center gap-3 flex-1 justify-center max-w-xl">
            {/* Preset Selector */}
            <div className="relative flex-1 max-w-xs">
              <select
                value={selectedPresetId}
                onChange={(e) => loadPreset(e.target.value)}
                className="input-field appearance-none pr-8 text-xs cursor-pointer"
              >
                {SCENARIO_PRESETS.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.id}: {p.name}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-surface-400 pointer-events-none" />
            </div>
          </div>

          {/* Right controls */}
          <div className="flex items-center gap-2 shrink-0">
            <HealthBadge />

            {/* Backend URL */}
            <div className="relative">
              <button
                onClick={() => setShowUrlInput(!showUrlInput)}
                className="p-2 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-500 transition-colors cursor-pointer"
                title="Backend URL"
              >
                <Server className="w-4 h-4" />
              </button>
              {showUrlInput && (
                <div className="absolute right-0 top-full mt-2 w-72 p-3 card shadow-lg animate-fade-in z-50">
                  <label className="text-xs font-medium text-surface-500 mb-1 block">
                    Backend Base URL
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="url"
                      value={backendUrl}
                      onChange={(e) => setBackendUrl(e.target.value)}
                      className="input-field text-xs font-mono flex-1"
                      placeholder="http://localhost:8000"
                    />
                    <button onClick={applyUrl} className="btn-primary text-xs px-3 py-1.5">
                      Set
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg hover:bg-surface-100 dark:hover:bg-surface-800 text-surface-500 transition-colors cursor-pointer"
              title="Toggle theme"
            >
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </header>

      {/* ════════════════ MAIN LAYOUT ════════════════ */}
      <main className="flex-1 max-w-[1440px] mx-auto w-full px-4 sm:px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* ──── LEFT PANEL: Configuration ──── */}
          <aside className="lg:col-span-4 xl:col-span-3 space-y-4">
            {/* Scenario ID */}
            <div className="card card-body space-y-4">
              <div>
                <label className="flex items-center gap-2 text-sm font-semibold text-surface-700 dark:text-surface-300 mb-2">
                  <Settings className="w-4 h-4 text-surface-400" />
                  Scenario ID
                </label>
                <input
                  type="text"
                  value={scenarioId}
                  onChange={(e) => setScenarioId(e.target.value)}
                  className="input-field font-mono"
                  placeholder="GRID-101"
                />
              </div>

              {/* Operator Notes */}
              <OperatorNotesInput
                notes={operatorNotes}
                onChange={setOperatorNotes}
              />

              {/* Battery Config */}
              <BatterySettingsCard config={battery} onChange={setBattery} />
            </div>

            {/* Hourly Profile */}
            <div className="card card-body">
              <HourlyProfileTable hours={hours} onChange={setHours} />
            </div>

            {/* Run Button */}
            <button
              onClick={handleOptimize}
              disabled={mutation.isPending}
              className="btn-primary w-full text-base py-3"
            >
              {mutation.isPending ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Optimizing…
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  Run Optimization
                </>
              )}
            </button>

            {/* Latency */}
            {latencyMs !== null && (
              <div className="text-center text-xs text-surface-400 font-mono animate-fade-in">
                Completed in {(latencyMs / 1000).toFixed(2)}s
                {latencyMs > 5000 && (
                  <span className="text-volt-500 ml-1">(slow)</span>
                )}
              </div>
            )}
          </aside>

          {/* ──── RIGHT PANEL: Results ──── */}
          <section className="lg:col-span-8 xl:col-span-9 space-y-5">
            {/* KPI Cards */}
            <SummaryCards
              result={result}
              initialEnergy={battery.initial_energy_kwh}
              isLoading={mutation.isPending}
            />

            {/* Directive Inspector */}
            <DirectiveInspector
              directives={result?.directive_interpretation ?? []}
              operatorNotes={operatorNotes}
            />

            {/* Charts */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
              <div className="xl:col-span-2">
                <ScheduleChart
                  plan={result?.hourly_plan ?? []}
                  inputHours={hours}
                />
              </div>
              <div className="xl:col-span-2">
                <BatterySocChart
                  plan={result?.hourly_plan ?? []}
                  minimumEnergy={battery.minimum_energy_kwh}
                  capacity={battery.capacity_kwh}
                />
              </div>
            </div>

            {/* Dispatch Table */}
            <DispatchTable plan={result?.hourly_plan ?? []} />

            {/* Plan Summary */}
            {result?.plan_summary && (
              <div className="card animate-slide-up">
                <div className="card-header">
                  <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 flex items-center gap-2">
                    <FileText className="w-4 h-4 text-grid-500" />
                    Plan Summary
                  </h3>
                </div>
                <div className="card-body">
                  <p className="text-sm text-surface-600 dark:text-surface-400 leading-relaxed whitespace-pre-wrap">
                    {result.plan_summary}
                  </p>
                </div>
              </div>
            )}
          </section>
        </div>
      </main>

      {/* ════════════════ FOOTER ════════════════ */}
      <footer className="border-t border-surface-200 dark:border-surface-800 py-4 mt-8">
        <div className="max-w-[1440px] mx-auto px-4 sm:px-6 flex items-center justify-between text-xs text-surface-400">
          <span>GridWise Energy Optimizer — Smart Campus Dashboard</span>
          <span className="font-mono">v1.0.0</span>
        </div>
      </footer>
    </div>
  );
}
