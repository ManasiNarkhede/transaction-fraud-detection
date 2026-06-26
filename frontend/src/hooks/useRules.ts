import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { rulesApi } from '../api/rules';
import { RuleCreatePayload, RuleUpdatePayload } from '../types';

const RULES_KEY = ['rules'];

export const useRules = () => {
  return useQuery({
    queryKey: RULES_KEY,
    queryFn: () => rulesApi.list(),
  });
};

export const useRuleMutations = () => {
  const queryClient = useQueryClient();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: RULES_KEY });

  const createRule = useMutation({
    mutationFn: (payload: RuleCreatePayload) => rulesApi.create(payload),
    onSuccess: invalidate,
  });

  const updateRule = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: RuleUpdatePayload }) =>
      rulesApi.update(id, payload),
    onSuccess: invalidate,
  });

  const deleteRule = useMutation({
    mutationFn: (id: string) => rulesApi.remove(id),
    onSuccess: invalidate,
  });

  const activateRule = useMutation({
    mutationFn: (id: string) => rulesApi.activate(id),
    onSuccess: invalidate,
  });

  const deactivateRule = useMutation({
    mutationFn: (id: string) => rulesApi.deactivate(id),
    onSuccess: invalidate,
  });

  return { createRule, updateRule, deleteRule, activateRule, deactivateRule };
};
