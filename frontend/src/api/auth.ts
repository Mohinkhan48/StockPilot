/**
 * frontend/src/api/auth.ts
 * Authentication endpoints matching Django accounts API.
 */

import { apiClient } from './client';
import { AuthResponse, MeResponse } from '../types';

export const authApi = {
  login: async (credentials: { username: string; password: string }): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/auth/login/', credentials);
    return response.data;
  },

  register: async (data: { username: string; email?: string; password: string }): Promise<AuthResponse> => {
    const response = await apiClient.post<AuthResponse>('/auth/register/', data);
    return response.data;
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout/');
  },

  getMe: async (): Promise<MeResponse> => {
    const response = await apiClient.get<MeResponse>('/auth/me/');
    return response.data;
  },
};
