import { Plus, Trash2 } from 'lucide-react';
import { FC, useCallback, useId } from 'react';

import {
  ConditionBuilderState,
  ConditionRow,
  RULE_FIELDS,
  RULE_OPERATORS,
  createEmptyConditionRow,
} from '../utils/ruleConditionUtils';

interface RuleConditionBuilderProps {
  state: ConditionBuilderState;
  onChange: (state: ConditionBuilderState) => void;
}

const selectClass =
  'rounded-md border border-gray-300 bg-white px-2 py-2 text-sm text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500';

const inputClass =
  'min-w-0 flex-1 rounded-md border border-gray-300 bg-white px-2 py-2 text-sm text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500';

export const RuleConditionBuilder: FC<RuleConditionBuilderProps> = ({ state, onChange }) => {
  const groupId = useId();

  const updateRow = useCallback(
    (id: string, patch: Partial<ConditionRow>) => {
      onChange({
        ...state,
        rows: state.rows.map((r) => (r.id === id ? { ...r, ...patch } : r)),
      });
    },
    [onChange, state]
  );

  const addRow = () => {
    onChange({ ...state, rows: [...state.rows, createEmptyConditionRow()] });
  };

  const removeRow = (id: string) => {
    if (state.rows.length <= 1) return;
    onChange({ ...state, rows: state.rows.filter((r) => r.id !== id) });
  };

  return (
    <div className="space-y-3" role="group" aria-labelledby={groupId}>
      <div className="flex items-center justify-between gap-2">
        <span id={groupId} className="text-xs font-medium text-gray-500">
          Match criteria
        </span>
        {state.rows.length > 1 && (
          <div className="flex items-center gap-1 text-xs">
            <span className="text-gray-500">Match</span>
            <select
              value={state.combinator}
              onChange={(e) =>
                onChange({ ...state, combinator: e.target.value as 'and' | 'or' })
              }
              className={`${selectClass} py-1 text-xs`}
              aria-label="Condition combinator"
            >
              <option value="and">ALL (AND)</option>
              <option value="or">ANY (OR)</option>
            </select>
          </div>
        )}
      </div>

      <div className="space-y-2">
        {state.rows.map((row, index) => (
          <div key={row.id}>
            {index > 0 && (
              <div className="mb-1 text-center text-xs font-semibold uppercase tracking-wide text-indigo-600">
                {state.combinator}
              </div>
            )}
            <div className="flex flex-wrap items-center gap-2 rounded-md border border-gray-200 bg-gray-50 p-2">
              <select
                value={row.field}
                onChange={(e) => updateRow(row.id, { field: e.target.value })}
                className={`${selectClass} w-36`}
                aria-label="Field"
              >
                {RULE_FIELDS.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>

              <select
                value={row.op}
                onChange={(e) => updateRow(row.id, { op: e.target.value })}
                className={`${selectClass} w-36`}
                aria-label="Operator"
              >
                {RULE_OPERATORS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>

              <input
                type="text"
                value={row.value}
                onChange={(e) => updateRow(row.id, { value: e.target.value })}
                className={inputClass}
                placeholder={
                  row.op === 'in' || row.op === 'not_in' ? 'US, GB, DE' : 'Value'
                }
                aria-label="Value"
              />

              <button
                type="button"
                onClick={() => removeRow(row.id)}
                disabled={state.rows.length <= 1}
                className="rounded-md p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-30"
                aria-label="Remove condition"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={addRow}
        className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-800"
      >
        <Plus className="h-3.5 w-3.5" />
        Add condition
      </button>
    </div>
  );
};
