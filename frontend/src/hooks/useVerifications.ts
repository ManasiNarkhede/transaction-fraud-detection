import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { verificationApi } from '../api/verification';
import { VerificationState } from '../types';

export const useVerificationQueue = (state: VerificationState) => {
  return useQuery({
    queryKey: ['verificationQueue', state],
    queryFn: () => verificationApi.getQueue({ state, limit: 100 }),
  });
};

export const useDeliverOtp = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      verificationId,
      channel,
    }: {
      verificationId: string;
      channel: 'email' | 'sms';
    }) => verificationApi.deliverOtp(verificationId, channel),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['verificationQueue'] });
    },
  });
};

export const useSubmitOtp = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ verificationId, otp }: { verificationId: string; otp: string }) =>
      verificationApi.submitOtp(verificationId, otp),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['verificationQueue'] });
    },
  });
};

export const useRejectVerification = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (verificationId: string) => verificationApi.reject(verificationId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['verificationQueue'] });
    },
  });
};
