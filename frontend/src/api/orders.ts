/**
 * frontend/src/api/orders.ts
 * Sales orders endpoints matching orders API.
 */

import { apiClient } from './client';
import { Order, OrderCreatePayload, OrderStatus, PaginatedResponse } from '../types';

export const ordersApi = {
  list: async (
    workspaceId: number,
    params?: { status?: OrderStatus; ordering?: string; page?: number }
  ): Promise<PaginatedResponse<Order>> => {
    const response = await apiClient.get<PaginatedResponse<Order>>(
      `/workspaces/${workspaceId}/orders/`,
      { params }
    );
    return response.data;
  },

  create: async (workspaceId: number, payload: OrderCreatePayload): Promise<Order> => {
    const response = await apiClient.post<Order>(
      `/workspaces/${workspaceId}/orders/`,
      payload
    );
    return response.data;
  },

  getDetail: async (workspaceId: number, orderId: number): Promise<Order> => {
    const response = await apiClient.get<Order>(
      `/workspaces/${workspaceId}/orders/${orderId}/`
    );
    return response.data;
  },

  delete: async (workspaceId: number, orderId: number): Promise<void> => {
    await apiClient.delete(`/workspaces/${workspaceId}/orders/${orderId}/`);
  },

  confirm: async (workspaceId: number, orderId: number): Promise<Order> => {
    const response = await apiClient.post<Order>(
      `/workspaces/${workspaceId}/orders/${orderId}/confirm/`
    );
    return response.data;
  },

  complete: async (workspaceId: number, orderId: number): Promise<Order> => {
    const response = await apiClient.post<Order>(
      `/workspaces/${workspaceId}/orders/${orderId}/complete/`
    );
    return response.data;
  },

  cancel: async (workspaceId: number, orderId: number): Promise<Order> => {
    const response = await apiClient.post<Order>(
      `/workspaces/${workspaceId}/orders/${orderId}/cancel/`
    );
    return response.data;
  },
};
