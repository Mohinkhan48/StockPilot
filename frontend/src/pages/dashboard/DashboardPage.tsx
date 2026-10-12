/**
 * frontend/src/pages/dashboard/DashboardPage.tsx
 * Live inventory and order metrics backed 100% by real Django REST endpoints.
 */

import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Package,
  AlertTriangle,
  ShoppingCart,
  ArrowLeftRight,
  TrendingUp,
  Clock,
  ArrowRight,
} from 'lucide-react';
import { productsApi } from '../../api/products';
import { ordersApi } from '../../api/orders';
import { InventoryMovement, Order, Product } from '../../types';
import { extractErrorMessage } from '../../api/client';

export const DashboardPage: React.FC = () => {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const wsId = parseInt(workspaceId || '', 10);

  const [totalProducts, setTotalProducts] = useState<number | null>(null);
  const [lowStockCount, setLowStockCount] = useState<number | null>(null);
  const [pendingOrdersCount, setPendingOrdersCount] = useState<number | null>(null);
  const [totalStockUnits, setTotalStockUnits] = useState<number | null>(null);

  const [recentMovements, setRecentMovements] = useState<InventoryMovement[]>([]);
  const [recentOrders, setRecentOrders] = useState<Order[]>([]);
  const [lowStockItems, setLowStockItems] = useState<Product[]>([]);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isNaN(wsId)) return;

    let isMounted = true;
    setIsLoading(true);
    setError(null);

    const loadDashboardData = async () => {
      try {
        // 1. Server-side aggregate metrics (total products, stock units, low stock count)
        //    Computed from a single DB query — never derived from a paginated page.
        const statsRes = await productsApi.getInventoryStats(wsId);
        // 2. Fetch low-stock product list for the dashboard widget (first 5)
        const lowStockRes = await productsApi.listLowStock(wsId, 1);
        // 3. Fetch pending orders count
        const pendingOrdersRes = await ordersApi.list(wsId, { status: 'pending', page: 1 });
        // 4. Fetch recent orders
        const ordersRes = await ordersApi.list(wsId, { page: 1 });
        // 5. Fetch recent movements
        const movementsRes = await productsApi.getWorkspaceMovements(wsId, { page: 1 });

        if (isMounted) {
          setTotalProducts(statsRes.total_active_products);
          setLowStockCount(statsRes.low_stock_count);
          setTotalStockUnits(statsRes.total_stock_units);
          setLowStockItems(lowStockRes.results.slice(0, 5));
          setPendingOrdersCount(pendingOrdersRes.count);

          setRecentOrders(ordersRes.results.slice(0, 5));
          setRecentMovements(movementsRes.results.slice(0, 5));
        }
      } catch (err) {
        if (isMounted) {
          setError(extractErrorMessage(err));
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    };

    loadDashboardData();
    return () => {
      isMounted = false;
    };
  }, [wsId]);

  if (isLoading) {
    return (
      <div>
        <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '1.5rem' }}>Dashboard Overview</h1>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="card" style={{ height: '110px', opacity: 0.6 }}>
              Loading metrics...
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card" style={{ borderLeft: '4px solid var(--status-danger)' }}>
        <h3 style={{ color: 'var(--status-danger)', marginBottom: '0.5rem' }}>Error Loading Dashboard</h3>
        <p style={{ color: 'var(--text-secondary)' }}>{error}</p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.75rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>Warehouse Dashboard</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Real-time catalog, inventory levels, and order fulfillment status
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <Link to={`/workspaces/${wsId}/products`} className="btn btn-secondary btn-sm">
            <Package size={14} />
            <span>View Products</span>
          </Link>
          <Link to={`/workspaces/${wsId}/orders`} className="btn btn-primary btn-sm">
            <ShoppingCart size={14} />
            <span>Manage Orders</span>
          </Link>
        </div>
      </div>

      {/* 4 Key Metric Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem', marginBottom: '2rem' }}>
        {/* Metric 1: Total Products */}
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: 'var(--radius-lg)',
              backgroundColor: 'rgba(99, 102, 241, 0.15)',
              color: 'var(--brand-primary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Package size={24} />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
              Catalog SKUs
            </span>
            <div style={{ fontSize: '1.6rem', fontWeight: 700 }}>{totalProducts ?? 0}</div>
          </div>
        </div>

        {/* Metric 2: Low-Stock Alerts */}
        <div
          className="card"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '1rem',
            borderColor: (lowStockCount ?? 0) > 0 ? 'var(--status-danger-border)' : 'var(--border-subtle)',
          }}
        >
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: 'var(--radius-lg)',
              backgroundColor: (lowStockCount ?? 0) > 0 ? 'var(--status-danger-bg)' : 'rgba(100, 116, 139, 0.15)',
              color: (lowStockCount ?? 0) > 0 ? 'var(--status-danger)' : 'var(--text-muted)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <AlertTriangle size={24} />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
              Low-Stock Alerts
            </span>
            <div style={{ fontSize: '1.6rem', fontWeight: 700, color: (lowStockCount ?? 0) > 0 ? 'var(--status-danger)' : 'inherit' }}>
              {lowStockCount ?? 0}
            </div>
          </div>
        </div>

        {/* Metric 3: Pending Orders */}
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: 'var(--radius-lg)',
              backgroundColor: 'var(--status-warning-bg)',
              color: 'var(--status-warning)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Clock size={24} />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
              Pending Orders
            </span>
            <div style={{ fontSize: '1.6rem', fontWeight: 700 }}>{pendingOrdersCount ?? 0}</div>
          </div>
        </div>

        {/* Metric 4: Total Units (Page sample) */}
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: 'var(--radius-lg)',
              backgroundColor: 'var(--status-success-bg)',
              color: 'var(--status-success)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <TrendingUp size={24} />
          </div>
          <div>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
              Total Units (Active)
            </span>
            <div style={{ fontSize: '1.6rem', fontWeight: 700 }}>{totalStockUnits ?? 0}</div>
          </div>
        </div>
      </div>

      {/* Grid: Low Stock Alert Banner + Recent Activity */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '1.5rem' }}>
        {/* Low Stock Watchlist */}
        <div className="card">
          <div className="card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <AlertTriangle size={18} color="var(--status-danger)" />
              <h2 className="card-title">Low-Stock Watchlist</h2>
            </div>
            <Link to={`/workspaces/${wsId}/products`} className="btn btn-ghost btn-sm">
              View All
            </Link>
          </div>

          {lowStockItems.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', padding: '1rem 0' }}>
              ✓ All inventory items are currently above their low-stock thresholds.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {lowStockItems.map((item) => (
                <div
                  key={item.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.75rem',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{item.name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>SKU: {item.sku}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span className="badge badge-danger">
                      {item.stock_quantity} left (min: {item.low_stock_threshold})
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Inventory Movements */}
        <div className="card">
          <div className="card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <ArrowLeftRight size={18} color="var(--brand-primary)" />
              <h2 className="card-title">Recent Stock Movements</h2>
            </div>
            <Link to={`/workspaces/${wsId}/inventory/movements`} className="btn btn-ghost btn-sm">
              Full Ledger
            </Link>
          </div>

          {recentMovements.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', padding: '1rem 0' }}>
              No inventory movements recorded yet.
            </p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              {recentMovements.map((m) => (
                <div
                  key={m.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.75rem',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--bg-surface-elevated)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{m.product_name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {m.movement_type.toUpperCase()} • {m.notes || 'No note'}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <span
                      style={{
                        fontSize: '0.85rem',
                        fontWeight: 700,
                        color: m.quantity >= 0 ? 'var(--status-success)' : 'var(--status-danger)',
                      }}
                    >
                      {m.quantity >= 0 ? `+${m.quantity}` : m.quantity} units
                    </span>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Post-stock: {m.resulting_stock}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
