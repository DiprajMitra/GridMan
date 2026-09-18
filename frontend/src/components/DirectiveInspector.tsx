import { useState } from 'react';
import { Eye, EyeOff, Code, CheckCircle2, XCircle, ChevronDown, ChevronUp } from 'lucide-react';
import type { DirectiveInterpretation, DirectiveType } from '../types/energy';

interface DirectiveInspectorProps {
  directives: DirectiveInterpretation[];
  operatorNotes: string[];
}

const DIRECTIVE_COLORS: Record<DirectiveType, { bg: string; text: string; label: string }> = {
  solar_reduction: {
    bg: 'bg-yellow-100 dark:bg-yellow-900/40',
    text: 'text-yellow-800 dark:text-yellow-400',
    label: 'Solar Reduction',
  },
  no_charge_window: {
    bg: 'bg-orange-100 dark:bg-orange-900/40',
    text: 'text-orange-800 dark:text-orange-400',
    label: 'No Charge Window',
  },
  minimum_battery_reserve: {
    bg: 'bg-cyan-100 dark:bg-cyan-900/40',
    text: 'text-cyan-800 dark:text-cyan-400',
    label: 'Min Battery Reserve',
  },
  max_grid_window: {
    bg: 'bg-indigo-100 dark:bg-indigo-900/40',
    text: 'text-indigo-800 dark:text-indigo-400',
    label: 'Max Grid Window',
  },
  no_op: {
    bg: 'bg-surface-100 dark:bg-surface-800',
    text: 'text-surface-600 dark:text-surface-400',
    label: 'No Operation',
  },
};

export default function DirectiveInspector({
  directives,
  operatorNotes,
}: DirectiveInspectorProps) {
  const [expandedJson, setExpandedJson] = useState<number | null>(null);

  if (!directives.length) {
    return (
      <div className="card">
        <div className="card-header">
          <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 flex items-center gap-2">
            <Eye className="w-4 h-4 text-grid-500" />
            Directive Interpretation
          </h3>
        </div>
        <div className="card-body text-center py-8">
          <EyeOff className="w-8 h-8 mx-auto text-surface-300 dark:text-surface-600 mb-2" />
          <p className="text-sm text-surface-400">
            Run optimization to see directive interpretations
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-surface-700 dark:text-surface-300 flex items-center gap-2">
            <Eye className="w-4 h-4 text-grid-500" />
            Directive Interpretation
          </h3>
          <div className="flex gap-2">
            <span className="badge bg-grid-100 text-grid-700 dark:bg-grid-900/40 dark:text-grid-400">
              {directives.filter((d) => d.applies).length} Active
            </span>
            <span className="badge bg-surface-100 text-surface-500 dark:bg-surface-800 dark:text-surface-400">
              {directives.filter((d) => !d.applies).length} Ignored
            </span>
          </div>
        </div>
      </div>
      <div className="card-body space-y-3">
        {directives.map((d, i) => {
          const colors = DIRECTIVE_COLORS[d.directive_type] ?? DIRECTIVE_COLORS.no_op;
          const note = operatorNotes[d.note_index] ?? '(unknown note)';
          const isExpanded = expandedJson === i;

          return (
            <div
              key={i}
              className={`rounded-lg border p-3 animate-slide-up transition-all ${
                d.applies
                  ? 'border-grid-200 dark:border-grid-800/50 bg-grid-50/50 dark:bg-grid-950/20'
                  : 'border-surface-200 dark:border-surface-700 bg-surface-50/50 dark:bg-surface-800/30'
              }`}
              style={{ animationDelay: `${i * 80}ms` }}
            >
              {/* Header */}
              <div className="flex items-start gap-3">
                <div className="mt-0.5">
                  {d.applies ? (
                    <CheckCircle2 className="w-5 h-5 text-grid-500" />
                  ) : (
                    <XCircle className="w-5 h-5 text-surface-400" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="text-xs font-mono text-surface-400">
                      #{d.note_index}
                    </span>
                    <span className={`badge ${colors.bg} ${colors.text}`}>
                      {colors.label}
                    </span>
                    <span
                      className={`badge ${
                        d.applies
                          ? 'bg-grid-100 text-grid-800 dark:bg-grid-900/50 dark:text-grid-400'
                          : 'bg-surface-100 text-surface-600 dark:bg-surface-800 dark:text-surface-400'
                      }`}
                    >
                      {d.applies ? 'Active Constraint' : 'Ignored Distractor'}
                    </span>
                  </div>
                  <p className="text-sm text-surface-600 dark:text-surface-400 italic truncate">
                    "{note}"
                  </p>
                  <p className="text-sm text-surface-700 dark:text-surface-300 mt-1">
                    {d.explanation}
                  </p>
                </div>
              </div>

              {/* JSON toggle */}
              {d.structured_adjustment && (
                <div className="mt-2 ml-8">
                  <button
                    onClick={() => setExpandedJson(isExpanded ? null : i)}
                    className="flex items-center gap-1 text-xs text-surface-400 hover:text-surface-600 dark:hover:text-surface-300 transition-colors cursor-pointer"
                  >
                    <Code className="w-3 h-3" />
                    {isExpanded ? 'Hide' : 'View'} structured adjustment
                    {isExpanded ? (
                      <ChevronUp className="w-3 h-3" />
                    ) : (
                      <ChevronDown className="w-3 h-3" />
                    )}
                  </button>
                  {isExpanded && (
                    <pre className="mt-2 p-3 rounded-lg bg-surface-900 dark:bg-surface-950 text-grid-400 text-xs font-mono overflow-x-auto animate-fade-in">
                      {JSON.stringify(d.structured_adjustment, null, 2)}
                    </pre>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
