import { isAxiosError } from 'axios';
import { Plus, Pencil, Trash2, PowerOff, Power, X, Check } from 'lucide-react';
import { FC, useState } from 'react';

import { InfoTooltip } from '../components/InfoTooltip';
import { RuleConditionBuilder } from '../components/RuleConditionBuilder';
import { RULE_FORM_FIELD_HELP } from '../constants/fieldHelp';
import { useRules, useRuleMutations } from '../hooks/useRules';
import { Rule, RuleCreatePayload } from '../types';
import {
  ConditionBuilderState,
  buildConditions,
  parseConditions,
} from '../utils/ruleConditionUtils';

const actionStyles: Record<string, string> = {
  approve: 'bg-green-100 text-green-800',
  verify: 'bg-yellow-100 text-yellow-800',
  block: 'bg-red-100 text-red-800',
};

interface FormState {
  name: string;
  description: string;
  rule_type: string;
  conditions: ConditionBuilderState;
  action: string;
  priority: number;
  score_value: number;
}

const emptyConditions = parseConditions(null);

const emptyForm: FormState = {
  name: '',
  description: '',
  rule_type: 'threshold',
  conditions: emptyConditions,
  action: 'block',
  priority: 1,
  score_value: 0,
};

const Rules: FC = () => {
  const { data: rules = [], isLoading, error } = useRules();
  const { createRule, updateRule, deleteRule, deactivateRule, activateRule } = useRuleMutations();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<Rule | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [formData, setFormData] = useState<FormState>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);

  const openCreateModal = () => {
    setEditingRule(null);
    setFormData(emptyForm);
    setFormError(null);
    setIsModalOpen(true);
  };

  const openEditModal = (rule: Rule) => {
    setEditingRule(rule);
    setFormData({
      name: rule.name,
      description: rule.description ?? '',
      rule_type: rule.rule_type,
      conditions: parseConditions(rule.conditions ?? {}),
      action: rule.action,
      priority: rule.priority,
      score_value: rule.score_value,
    });
    setFormError(null);
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditingRule(null);
    setFormError(null);
  };

  const handleSave = async () => {
    if (!formData.name.trim() || !formData.rule_type.trim()) {
      setFormError('Name and rule type are required.');
      return;
    }

    const payload: RuleCreatePayload = {
      name: formData.name.trim(),
      description: formData.description.trim() || null,
      rule_type: formData.rule_type.trim(),
      conditions: buildConditions(formData.conditions),
      action: formData.action,
      priority: formData.priority,
      score_value: formData.score_value,
    };

    try {
      if (editingRule) {
        await updateRule.mutateAsync({ id: editingRule.id, payload });
      } else {
        await createRule.mutateAsync(payload);
      }
      closeModal();
    } catch (err) {
      if (isAxiosError(err) && err.response?.status === 404) {
        setFormError('Rule not found.');
      } else {
        setFormError('Failed to save rule. Please try again.');
      }
    }
  };

  const handleDelete = async (id: string) => {
    setDeleteConfirmId(null);
    await deleteRule.mutateAsync(id).catch(() => undefined);
  };

  const isSaving = createRule.isPending || updateRule.isPending;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Rules Management</h1>
          <p className="mt-1 text-sm text-gray-500">
            Create and manage fraud detection rules — active and inactive
          </p>
        </div>
        <button
          onClick={openCreateModal}
          className="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          <Plus className="h-4 w-4" />
          New Rule
        </button>
      </div>

      {error && (
        <div className="rounded-md bg-red-50 p-4 text-sm text-red-700">
          Failed to load rules. Please try again.
        </div>
      )}

      <div className="rounded-lg border border-gray-200 bg-white shadow-sm">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Action
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Priority
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Score
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                  Status
                </th>
                <th className="px-6 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-sm text-gray-500">
                    Loading rules...
                  </td>
                </tr>
              ) : rules.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-sm text-gray-500">
                    No rules found
                  </td>
                </tr>
              ) : (
                rules.map((rule) => (
                  <tr key={rule.id} className={`hover:bg-gray-50 ${!rule.is_active ? 'opacity-60' : ''}`}>
                    <td className="whitespace-nowrap px-6 py-4 text-sm font-medium text-gray-900">
                      {rule.name}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-500">
                      {rule.rule_type}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${
                          actionStyles[rule.action] || 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {rule.action}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                      {rule.priority}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">
                      {rule.score_value}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${
                          rule.is_active
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {rule.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        {rule.is_active ? (
                          <button
                            onClick={() => deactivateRule.mutate(rule.id)}
                            className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                            title="Deactivate rule"
                          >
                            <PowerOff className="h-4 w-4" />
                          </button>
                        ) : (
                          <button
                            onClick={() => activateRule.mutate(rule.id)}
                            className="rounded-md p-1.5 text-green-600 hover:bg-green-50 hover:text-green-700"
                            title="Activate rule"
                          >
                            <Power className="h-4 w-4" />
                          </button>
                        )}
                        <button
                          onClick={() => openEditModal(rule)}
                          className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
                          title="Edit"
                        >
                          <Pencil className="h-4 w-4" />
                        </button>
                        {deleteConfirmId === rule.id ? (
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => handleDelete(rule.id)}
                              className="rounded-md p-1.5 text-red-600 hover:bg-red-50"
                              title="Confirm delete"
                            >
                              <Check className="h-4 w-4" />
                            </button>
                            <button
                              onClick={() => setDeleteConfirmId(null)}
                              className="rounded-md p-1.5 text-gray-500 hover:bg-gray-100"
                              title="Cancel"
                            >
                              <X className="h-4 w-4" />
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setDeleteConfirmId(rule.id)}
                            className="rounded-md p-1.5 text-gray-500 hover:bg-red-50 hover:text-red-600"
                            title="Delete"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {isModalOpen && (
        <RuleModal
          editing={!!editingRule}
          formData={formData}
          setFormData={setFormData}
          onClose={closeModal}
          onSave={handleSave}
          isSaving={isSaving}
          formError={formError}
        />
      )}
    </div>
  );
};

interface RuleModalProps {
  editing: boolean;
  formData: FormState;
  setFormData: React.Dispatch<React.SetStateAction<FormState>>;
  onClose: () => void;
  onSave: () => void;
  isSaving: boolean;
  formError: string | null;
}

const RuleModal: FC<RuleModalProps> = ({
  editing,
  formData,
  setFormData,
  onClose,
  onSave,
  isSaving,
  formError,
}) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
    <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">{editing ? 'Edit Rule' : 'New Rule'}</h2>
        <button
          onClick={onClose}
          className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="space-y-4">
        <Field label="Name" tooltip={RULE_FORM_FIELD_HELP.name}>
          <input
            type="text"
            value={formData.name}
            onChange={(e) => setFormData((p) => ({ ...p, name: e.target.value }))}
            className={inputClass}
            placeholder="Rule name"
          />
        </Field>

        <Field label="Description" tooltip={RULE_FORM_FIELD_HELP.description}>
          <input
            type="text"
            value={formData.description}
            onChange={(e) => setFormData((p) => ({ ...p, description: e.target.value }))}
            className={inputClass}
            placeholder="Optional"
          />
        </Field>

        <Field label="Rule Type" tooltip={RULE_FORM_FIELD_HELP.rule_type}>
          <input
            type="text"
            value={formData.rule_type}
            onChange={(e) => setFormData((p) => ({ ...p, rule_type: e.target.value }))}
            className={inputClass}
            placeholder="e.g. threshold, velocity"
          />
        </Field>

        <div className="flex flex-col gap-1">
          <span className="flex items-center gap-0.5 text-xs font-medium text-gray-500">
            Conditions
            <InfoTooltip text={RULE_FORM_FIELD_HELP.conditions} />
          </span>
          <RuleConditionBuilder
            state={formData.conditions}
            onChange={(conditions) => setFormData((p) => ({ ...p, conditions }))}
          />
        </div>

        <Field label="Action" tooltip={RULE_FORM_FIELD_HELP.action}>
          <select
            value={formData.action}
            onChange={(e) => setFormData((p) => ({ ...p, action: e.target.value }))}
            className={inputClass}
          >
            <option value="block">Block</option>
            <option value="verify">Verify</option>
            <option value="approve">Approve</option>
          </select>
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Priority" tooltip={RULE_FORM_FIELD_HELP.priority}>
            <input
              type="number"
              min={1}
              value={formData.priority}
              onChange={(e) =>
                setFormData((p) => ({ ...p, priority: parseInt(e.target.value, 10) || 1 }))
              }
              className={inputClass}
            />
          </Field>
          <Field label="Score Value" tooltip={RULE_FORM_FIELD_HELP.score_value}>
            <input
              type="number"
              value={formData.score_value}
              onChange={(e) =>
                setFormData((p) => ({ ...p, score_value: parseInt(e.target.value, 10) || 0 }))
              }
              className={inputClass}
            />
          </Field>
        </div>

        {formError && (
          <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{formError}</div>
        )}
      </div>

      <div className="mt-6 flex justify-end gap-3">
        <button
          onClick={onClose}
          className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Cancel
        </button>
        <button
          onClick={onSave}
          disabled={isSaving}
          className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {isSaving ? 'Saving...' : editing ? 'Save Changes' : 'Create Rule'}
        </button>
      </div>
    </div>
  </div>
);

const inputClass =
  'w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500';

const Field: FC<{ label: string; tooltip: string; children: React.ReactNode }> = ({
  label,
  tooltip,
  children,
}) => (
  <div className="flex flex-col gap-1">
    <span className="flex items-center gap-0.5 text-xs font-medium text-gray-500">
      {label}
      <InfoTooltip text={tooltip} />
    </span>
    {children}
  </div>
);

export default Rules;
