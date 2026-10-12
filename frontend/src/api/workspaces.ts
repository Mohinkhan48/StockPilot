/**
 * frontend/src/api/workspaces.ts
 * Workspace multi-tenant management endpoints matching accounts API.
 */

import { apiClient } from './client';
import { Workspace, WorkspaceMembership } from '../types';

export const workspacesApi = {
  list: async (): Promise<Workspace[]> => {
    const response = await apiClient.get<Workspace[] | { results: Workspace[] }>('/workspaces/');
    // Handle both direct list or paginated response
    if (Array.isArray(response.data)) {
      return response.data;
    }
    return response.data.results || [];
  },

  create: async (data: { name: string }): Promise<Workspace> => {
    const response = await apiClient.post<Workspace>('/workspaces/', data);
    return response.data;
  },

  getDetail: async (id: number): Promise<Workspace> => {
    const response = await apiClient.get<Workspace>(`/workspaces/${id}/`);
    return response.data;
  },

  update: async (id: number, data: { name: string }): Promise<Workspace> => {
    const response = await apiClient.patch<Workspace>(`/workspaces/${id}/`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/workspaces/${id}/`);
  },

  listMembers: async (workspaceId: number): Promise<WorkspaceMembership[]> => {
    const response = await apiClient.get<WorkspaceMembership[]>(`/workspaces/${workspaceId}/members/`);
    return response.data;
  },

  addMember: async (
    workspaceId: number,
    data: { username: string; role: 'owner' | 'staff' }
  ): Promise<WorkspaceMembership> => {
    const response = await apiClient.post<WorkspaceMembership>(
      `/workspaces/${workspaceId}/members/`,
      data
    );
    return response.data;
  },

  removeMember: async (workspaceId: number, userId: number): Promise<void> => {
    await apiClient.delete(`/workspaces/${workspaceId}/members/${userId}/`);
  },
};
