import {
  ApiEnvelope,
  VerificationQueueResponse,
  VerificationState,
} from '../types';

import { apiClient } from './client';

interface QueueParams {
  state: VerificationState;
  limit?: number;
  offset?: number;
}

export interface DeliverOtpResult {
  verification_id: string;
  channel: string;
  contact_info: string | null;
  expires_at: string;
  delivery_attempted: boolean;
}

export interface SubmitOtpResult {
  state: string;
  message: string;
  success: boolean;
}

export const verificationApi = {
  getQueue: async (params: QueueParams): Promise<VerificationQueueResponse> => {
    const response = await apiClient.get<ApiEnvelope<VerificationQueueResponse>>(
      '/verify/queue',
      { params }
    );
    return (
      response.data.data ?? {
        total: 0,
        limit: params.limit ?? 50,
        offset: params.offset ?? 0,
        items: [],
      }
    );
  },

  deliverOtp: async (
    verificationId: string,
    channel: 'email' | 'sms'
  ): Promise<DeliverOtpResult> => {
    const response = await apiClient.post<ApiEnvelope<DeliverOtpResult>>(
      `/verify/${verificationId}/deliver-otp`,
      { channel }
    );
    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error?.message ?? 'Failed to send OTP');
    }
    return response.data.data;
  },

  submitOtp: async (verificationId: string, otp: string): Promise<SubmitOtpResult> => {
    const response = await apiClient.post<ApiEnvelope<SubmitOtpResult>>('/verify/otp', {
      verification_id: verificationId,
      otp,
    });
    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error?.message ?? 'OTP verification failed');
    }
    return response.data.data;
  },

  reject: async (
    verificationId: string
  ): Promise<{ verification_id: string; state: string; transaction_id: string; message: string }> => {
    const response = await apiClient.post<
      ApiEnvelope<{ verification_id: string; state: string; transaction_id: string; message: string }>
    >(`/verify/${verificationId}/reject`);
    if (!response.data.success || !response.data.data) {
      throw new Error(response.data.error?.message ?? 'Rejection failed');
    }
    return response.data.data;
  },
};
