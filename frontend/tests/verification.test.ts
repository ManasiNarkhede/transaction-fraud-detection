import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../src/api/client', () => ({
  apiClient: { post: vi.fn(), get: vi.fn() },
}));

import { apiClient } from '../src/api/client';
import { verificationApi } from '../src/api/verification';

describe('verificationApi', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('unwraps the { success, data } envelope from the queue endpoint', async () => {
    const payload = {
      total: 1,
      limit: 100,
      offset: 0,
      items: [
        {
          verification_id: 'v1',
          transaction_id: 't1',
          user_id: 'u1',
          state: 'PENDING',
          channel: null,
          contact_info: null,
          attempts: 0,
          max_attempts: 3,
          created_at: '2026-06-23T10:00:00Z',
          expires_at: null,
          amount: '500.00',
          currency: 'USD',
          risk_score: 55,
        },
      ],
    };
    (apiClient.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { success: true, data: payload },
    });

    const result = await verificationApi.getQueue({ state: 'PENDING', limit: 100 });

    expect(apiClient.get).toHaveBeenCalledWith('/verify/queue', {
      params: { state: 'PENDING', limit: 100 },
    });
    expect(result.items).toHaveLength(1);
    expect(result.items[0].verification_id).toBe('v1');
  });

  it('delivers OTP via the deliver-otp endpoint', async () => {
    (apiClient.post as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        success: true,
        data: {
          verification_id: 'v1',
          channel: 'email',
          contact_info: 'u***@e***.com',
          expires_at: '2026-06-23T10:10:00Z',
          delivery_attempted: true,
        },
      },
    });

    const result = await verificationApi.deliverOtp('v1', 'email');

    expect(apiClient.post).toHaveBeenCalledWith('/verify/v1/deliver-otp', { channel: 'email' });
    expect(result.delivery_attempted).toBe(true);
  });

  it('throws on an error envelope when delivering OTP', async () => {
    (apiClient.post as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { success: false, error: { code: 'BAD_REQUEST', message: 'not pending' } },
    });

    await expect(verificationApi.deliverOtp('v1', 'sms')).rejects.toThrow('not pending');
  });
});
