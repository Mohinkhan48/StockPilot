/**
 * frontend/src/types/index.ts
 * Type definitions matching the exact Django REST Framework serializers and models.
 */

export interface User {
  id: number;
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface WorkspaceMembership {
  id: number;
  user: User;
  role: 'owner' | 'staff';
  joined_at: string;
}

export interface Workspace {
  id: number;
  name: string;
  owner: User;
  role: 'owner' | 'staff' | null;
  created_at: string;
}

export interface MeResponse {
  user: User;
  workspaces: Workspace[];
}

export interface Product {
  id: number;
  name: string;
  sku: string;
  description: string;
  price: string; // Decimal returned as string from DRF
  stock_quantity: number;
  low_stock_threshold: number;
  is_active: boolean;
  is_low_stock: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProductCreatePayload {
  name: string;
  sku: string;
  description?: string;
  price: string | number;
  stock_quantity?: number;
  low_stock_threshold?: number;
  is_active?: boolean;
}

export type MovementType = 'restock' | 'sale' | 'adjustment' | 'return';

export interface InventoryMovement {
  id: number;
  product: number;
  product_name: string;
  product_sku: string;
  movement_type: MovementType;
  quantity: number; // positive = in, negative = out
  resulting_stock: number;
  notes: string;
  created_by: User | null;
  order: number | null;
  created_at: string;
}

export interface RestockPayload {
  quantity: number;
  notes?: string;
}

export interface AdjustStockPayload {
  quantity: number;
  notes: string;
}

export type OrderStatus = 'pending' | 'confirmed' | 'completed' | 'cancelled';

export interface OrderItem {
  id: number;
  product_id: number;
  live_product_name: string;
  live_product_sku: string;
  live_product_price?: string | null;
  product_name: string;
  product_sku: string;
  unit_price: string | null;
  quantity: number;
  line_total: string;
  estimated_line_total: string;
}

export interface Order {
  id: number;
  workspace: number;
  workspace_name: string;
  created_by: User;
  status: OrderStatus;
  notes: string;
  items: OrderItem[];
  total: string; // Server-computed Decimal total
  estimated_total: string; // Server-computed estimated total
  created_at: string;
  updated_at: string;
}

export interface OrderItemCreatePayload {
  product_id: number;
  quantity: number;
}

export interface OrderCreatePayload {
  notes?: string;
  items: OrderItemCreatePayload[];
}

export interface InventoryStats {
  total_products: number;
  total_active_products: number;
  total_stock_units: number;
  low_stock_count: number;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
