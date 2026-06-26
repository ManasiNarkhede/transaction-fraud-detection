import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../src/api/client', () => ({
  apiClient: { post: vi.fn(), get: vi.fn() },
}));

import { authApi } from '../src/api/auth';
import { apiClient } from '../src/api/client';

describe('authApi.login', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('posts username (not email) to /auth/login', async () => {
    (apiClient.post as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { access_token: 'a', refresh_token: 'r', token_type: 'bearer' },
    });

    await authApi.login({ username: 'analyst', password: 'secret' });

    expect(apiClient.post).toHaveBeenCalledWith('/auth/login', {
      username: 'analyst',
      password: 'secret',
    });
  });
});

describe('authApi.register', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('posts email, phone, password to /auth/register', async () => {
    (apiClient.post as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { access_token: 'a', refresh_token: 'r', token_type: 'bearer' },
    });

    await authApi.register({
      email: 'new@example.com',
      phone: '+15550100',
      password: 'Secret123!',
    });

    expect(apiClient.post).toHaveBeenCalledWith('/auth/register', {
      email: 'new@example.com',
      phone: '+15550100',
      password: 'Secret123!',
    });
  });
});
