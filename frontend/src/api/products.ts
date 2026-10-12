/**
 * frontend/src/api/products.ts
 * Product catalog, stock adjustments, and movements matching inventory API.
 */

import { apiClient } from './client';
import {
  AdjustStockPayload,
  InventoryMovement,
  InventoryStats,
  PaginatedResponse,
  Product,
  ProductCreatePayload,
  RestockPayload,
} from '../types';

export const productsApi = {
  list: async (
    workspaceId: number,
    params?: { search?: string; ordering?: string; is_active?: boolean; low_stock?: boolean; page?: number }
  ): Promise<PaginatedResponse<Product>> => {
    const response = await apiClient.get<PaginatedResponse<Product>>(
      `/workspaces/${workspaceId}/products/`,
      { params }
    );
    return response.data;
  },

  listLowStock: async (workspaceId: number, page?: number): Promise<PaginatedResponse<Product>> => {
    const response = await apiClient.get<PaginatedResponse<Product>>(
      `/workspaces/${workspaceId}/products/low-stock/`,
      { params: { page } }
    );
    return response.data;
  },

  create: async (workspaceId: number, payload: ProductCreatePayload): Promise<Product> => {
    const response = await apiClient.post<Product>(
      `/workspaces/${workspaceId}/products/`,
      payload
    );
    return response.data;
  },

  getDetail: async (workspaceId: number, productId: number): Promise<Product> => {
    const response = await apiClient.get<Product>(
      `/workspaces/${workspaceId}/products/${productId}/`
    );
    return response.data;
  },

  update: async (
    workspaceId: number,
    productId: number,
    payload: Partial<ProductCreatePayload>
  ): Promise<Product> => {
    const response = await apiClient.patch<Product>(
      `/workspaces/${workspaceId}/products/${productId}/`,
      payload
    );
    return response.data;
  },

  delete: async (workspaceId: number, productId: number): Promise<void> => {
    await apiClient.delete(`/workspaces/${workspaceId}/products/${productId}/`);
  },

  restock: async (
    workspaceId: number,
    productId: number,
    payload: RestockPayload
  ): Promise<Product> => {
    const response = await apiClient.post<Product>(
      `/workspaces/${workspaceId}/products/${productId}/restock/`,
      payload
    );
    return response.data;
  },

  adjustStock: async (
    workspaceId: number,
    productId: number,
    payload: AdjustStockPayload
  ): Promise<Product> => {
    const response = await apiClient.post<Product>(
      `/workspaces/${workspaceId}/products/${productId}/adjust/`,
      payload
    );
    return response.data;
  },

  getProductMovements: async (
    workspaceId: number,
    productId: number,
    page?: number
  ): Promise<PaginatedResponse<InventoryMovement>> => {
    const response = await apiClient.get<PaginatedResponse<InventoryMovement>>(
      `/workspaces/${workspaceId}/products/${productId}/movements/`,
      { params: { page } }
    );
    return response.data;
  },

  getWorkspaceMovements: async (
    workspaceId: number,
    params?: { movement_type?: string; product_id?: number; page?: number }
  ): Promise<PaginatedResponse<InventoryMovement>> => {
    const response = await apiClient.get<PaginatedResponse<InventoryMovement>>(
      `/workspaces/${workspaceId}/inventory/movements/`,
      { params }
    );
    return response.data;
  },

  getInventoryStats: async (workspaceId: number): Promise<InventoryStats> => {
    const response = await apiClient.get<InventoryStats>(
      `/workspaces/${workspaceId}/inventory/stats/`
    );
    return response.data;
  },
};
