/** Fields available in the backend rule evaluation context. */
export const RULE_FIELDS: { value: string; label: string; type: 'string' | 'number' | 'boolean' }[] =
  [
    { value: 'amount', label: 'Amount', type: 'number' },
    { value: 'currency', label: 'Currency', type: 'string' },
    { value: 'user_id', label: 'User ID', type: 'string' },
    { value: 'merchant_id', label: 'Merchant ID', type: 'string' },
    { value: 'merchant_category', label: 'Merchant Category', type: 'string' },
    { value: 'location', label: 'Location / Country', type: 'string' },
    { value: 'device_id', label: 'Device ID', type: 'string' },
    { value: 'ip_address', label: 'IP Address', type: 'string' },
    { value: 'payment_method', label: 'Payment Method', type: 'string' },
    { value: 'hour_of_day', label: 'Hour of Day (0–23)', type: 'number' },
  ];

export const RULE_OPERATORS: { value: string; label: string }[] = [
  { value: 'eq', label: 'equals' },
  { value: 'ne', label: 'not equals' },
  { value: 'gt', label: 'greater than' },
  { value: 'lt', label: 'less than' },
  { value: 'gte', label: 'greater or equal' },
  { value: 'lte', label: 'less or equal' },
  { value: 'in', label: 'in list' },
  { value: 'not_in', label: 'not in list' },
  { value: 'contains', label: 'contains' },
  { value: 'regex', label: 'matches regex' },
];

export interface ConditionRow {
  id: string;
  field: string;
  op: string;
  value: string;
}

export interface ConditionBuilderState {
  combinator: 'and' | 'or';
  rows: ConditionRow[];
}

function newRow(): ConditionRow {
  return {
    id: crypto.randomUUID(),
    field: 'amount',
    op: 'gt',
    value: '1000',
  };
}

function isFieldCondition(obj: unknown): obj is { field: string; op: string; value: unknown } {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'field' in obj &&
    'op' in obj &&
    typeof (obj as { field: unknown }).field === 'string'
  );
}

function rowFromCondition(c: { field: string; op: string; value: unknown }): ConditionRow {
  let valueStr: string;
  if (Array.isArray(c.value)) {
    valueStr = c.value.map(String).join(', ');
  } else if (typeof c.value === 'boolean') {
    valueStr = c.value ? 'true' : 'false';
  } else {
    valueStr = c.value == null ? '' : String(c.value);
  }
  return {
    id: crypto.randomUUID(),
    field: c.field,
    op: c.op,
    value: valueStr,
  };
}

export function parseConditions(
  conditions: Record<string, unknown> | null | undefined
): ConditionBuilderState {
  const fallback: ConditionBuilderState = { combinator: 'and', rows: [newRow()] };
  if (!conditions || Object.keys(conditions).length === 0) {
    return fallback;
  }

  if (isFieldCondition(conditions)) {
    return { combinator: 'and', rows: [rowFromCondition(conditions)] };
  }

  if ('and' in conditions && Array.isArray(conditions.and)) {
    const rows = conditions.and.filter(isFieldCondition).map(rowFromCondition);
    if (rows.length > 0) {
      return { combinator: 'and', rows };
    }
  }

  if ('or' in conditions && Array.isArray(conditions.or)) {
    const rows = conditions.or.filter(isFieldCondition).map(rowFromCondition);
    if (rows.length > 0) {
      return { combinator: 'or', rows };
    }
  }

  return fallback;
}

function fieldMeta(field: string) {
  return (
    RULE_FIELDS.find((f) => f.value === field) ?? {
      value: field,
      label: field,
      type: 'string' as const,
    }
  );
}

function parseValue(
  field: string,
  op: string,
  raw: string
): string | number | boolean | string[] {
  const trimmed = raw.trim();
  const meta = fieldMeta(field);

  if (op === 'in' || op === 'not_in') {
    return trimmed
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
  }

  if (meta.type === 'number') {
    const n = Number(trimmed);
    return Number.isNaN(n) ? 0 : n;
  }
  if (meta.type === 'boolean') {
    return trimmed.toLowerCase() === 'true';
  }

  return trimmed;
}

export function buildConditions(state: ConditionBuilderState): Record<string, unknown> {
  const clauses = state.rows
    .filter((r) => r.field && r.op)
    .map((row) => ({
      field: row.field,
      op: row.op,
      value: parseValue(row.field, row.op, row.value),
    }));

  if (clauses.length === 0) {
    return { field: 'amount', op: 'gt', value: 0 };
  }
  if (clauses.length === 1) {
    return clauses[0];
  }
  return { [state.combinator]: clauses };
}

export function createEmptyConditionRow(): ConditionRow {
  return newRow();
}
