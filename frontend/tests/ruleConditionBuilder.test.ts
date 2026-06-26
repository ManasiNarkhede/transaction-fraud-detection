import { describe, it, expect } from 'vitest';

import { buildConditions, parseConditions } from '../src/utils/ruleConditionUtils';

describe('RuleConditionBuilder helpers', () => {
  it('parses a single field condition', () => {
    const state = parseConditions({ field: 'amount', op: 'gt', value: 5000 });
    expect(state.combinator).toBe('and');
    expect(state.rows).toHaveLength(1);
    expect(state.rows[0].field).toBe('amount');
    expect(state.rows[0].op).toBe('gt');
    expect(state.rows[0].value).toBe('5000');
  });

  it('builds a single field condition without wrapping combinator', () => {
    const state = parseConditions({ field: 'amount', op: 'gt', value: 1000 });
    expect(buildConditions(state)).toEqual({ field: 'amount', op: 'gt', value: 1000 });
  });

  it('round-trips AND conditions', () => {
    const original = {
      and: [
        { field: 'amount', op: 'gt', value: 1000 },
        { field: 'location', op: 'eq', value: 'NG' },
      ],
    };
    const state = parseConditions(original);
    expect(state.combinator).toBe('and');
    expect(state.rows).toHaveLength(2);
    expect(buildConditions(state)).toEqual(original);
  });

  it('parses in-list values as comma-separated strings', () => {
    const state = parseConditions({
      field: 'location',
      op: 'in',
      value: ['US', 'CA'],
    });
    expect(state.rows[0].value).toBe('US, CA');
    expect(buildConditions(state)).toEqual({
      field: 'location',
      op: 'in',
      value: ['US', 'CA'],
    });
  });
});
