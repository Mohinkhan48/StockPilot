/**
 * frontend/src/pages/orders/OrderListPage.tsx
 * Sales order list with lifecycle tabs, filters, and multi-item order creation drawer.
 */

import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ShoppingCart, Plus, Clock, CheckCircle2, XCircle, Trash2, AlertCircle } from 'lucide-react';
import { ordersApi } from '../../api/orders';
import { productsApi } from '../../api/products';
import { Order, OrderStatus, Product } from '../../types';
import { extractErrorMessage } from '../../api/client';

export const OrderListPage: React.FC = () => {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const wsId = parseInt(workspaceId || '', 10);

  const [orders, setOrders] = useState<Order[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState<number>(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New Order Drawer states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [availableProducts, setAvailableProducts] = useState<Product[]>([]);
  const [orderItems, setOrderItems] = useState<{ product_id: number; quantity: number }[]>([
    { product_id: 0, quantity: 1 },
  ]);
  const [orderNotes, setOrderNotes] = useState('');
  const [createError, setCreateError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchOrders = async () => {
    if (isNaN(wsId)) return;
    setIsLoading(true);
    setError(null);

    try {
      const params: any = { page };
      if (statusFilter !== 'all') {
        params.status = statusFilter;
      }
      const data = await ordersApi.list(wsId, params);
      setOrders(data.results);
      setTotalCount(data.count);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders();
  }, [wsId, page, statusFilter]);

  // Load products when opening create modal
  const handleOpenCreateModal = async () => {
    setCreateError(null);
    setShowCreateModal(true);
    try {
      const data = await productsApi.list(wsId, { is_active: true });
      setAvailableProducts(data.results);
      if (data.results.length > 0) {
        setOrderItems([{ product_id: data.results[0].id, quantity: 1 }]);
      }
    } catch (err) {
      setCreateError(extractErrorMessage(err));
    }
  };

  const handleAddItemRow = () => {
    if (availableProducts.length > 0) {
      setOrderItems([...orderItems, { product_id: availableProducts[0].id, quantity: 1 }]);
    }
  };

  const handleRemoveItemRow = (index: number) => {
    setOrderItems(orderItems.filter((_, i) => i !== index));
  };

  const handleCreateOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    setIsSubmitting(true);

    try {
      // Validate unique products
      const selectedIds = orderItems.map((item) => item.product_id);
      if (new Set(selectedIds).size !== selectedIds.length) {
        throw new Error('Duplicate product in order. Consolidate into a single line item.');
      }

      await ordersApi.create(wsId, {
        notes: orderNotes,
        items: orderItems,
      });

      setShowCreateModal(false);
      setOrderNotes('');
      setPage(1);
      await fetchOrders();
    } catch (err) {
      setCreateError(extractErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const getStatusBadge = (status: OrderStatus) => {
    switch (status) {
      case 'pending':
        return <span className="badge badge-pending">Pending</span>;
      case 'confirmed':
        return <span className="badge badge-confirmed">Confirmed</span>;
      case 'completed':
        return <span className="badge badge-completed">Completed</span>;
      case 'cancelled':
        return <span className="badge badge-cancelled">Cancelled</span>;
      default:
        return <span className="badge">{status}</span>;
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>Sales Orders</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Pending drafts, stock confirmation, warehouse fulfillment, and order cancellations
          </p>
        </div>

        <button onClick={handleOpenCreateModal} className="btn btn-primary btn-sm">
          <Plus size={16} />
          <span>New Sales Order</span>
        </button>
      </div>

      {/* Tabs */}
      <div
        className="card"
        style={{
          padding: '0.85rem 1.25rem',
          marginBottom: '1.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {[
            { id: 'all', label: 'All Orders' },
            { id: 'pending', label: 'Pending (Draft)' },
            { id: 'confirmed', label: 'Confirmed (Stock Locked)' },
            { id: 'completed', label: 'Completed (Fulfilled)' },
            { id: 'cancelled', label: 'Cancelled' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setStatusFilter(tab.id);
                setPage(1);
              }}
              className={`btn btn-sm ${statusFilter === tab.id ? 'btn-primary' : 'btn-ghost'}`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          {totalCount} total orders
        </span>
      </div>

      {error && (
        <div className="card" style={{ borderLeft: '4px solid var(--status-danger)', marginBottom: '1.5rem' }}>
          <p style={{ color: 'var(--status-danger)' }}>{error}</p>
        </div>
      )}

      {/* Orders Table */}
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Date Created</th>
              <th>Lines</th>
              <th>Created By</th>
              <th>Status</th>
              <th>Total Amount</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                  Loading sales orders...
                </td>
              </tr>
            ) : orders.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                  No orders found matching status filter.
                </td>
              </tr>
            ) : (
              orders.map((o) => (
                <tr key={o.id}>
                  <td style={{ fontWeight: 700 }}>
                    <Link
                      to={`/workspaces/${wsId}/orders/${o.id}`}
                      style={{ color: 'var(--brand-primary)' }}
                    >
                      #{o.id}
                    </Link>
                  </td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                    {new Date(o.created_at).toLocaleString()}
                  </td>
                  <td>{o.items.length} item(s)</td>
                  <td style={{ color: 'var(--text-secondary)' }}>{o.created_by?.username}</td>
                  <td>{getStatusBadge(o.status)}</td>
                  <td style={{ fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                    {o.status === 'pending' ? (
                      <div>
                        <div style={{ color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <span>${parseFloat(o.estimated_total || '0').toFixed(2)}</span>
                          <span
                            style={{
                              fontSize: '0.65rem',
                              padding: '0.1rem 0.35rem',
                              backgroundColor: 'rgba(245, 158, 11, 0.15)',
                              color: '#f59e0b',
                              borderRadius: '3px',
                              border: '1px solid rgba(245, 158, 11, 0.3)',
                              fontWeight: 700,
                              textTransform: 'uppercase',
                              letterSpacing: '0.04em',
                            }}
                          >
                            Draft
                          </span>
                        </div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 400, marginTop: '0.15rem' }}>
                          Prices lock upon confirmation
                        </div>
                      </div>
                    ) : (
                      <span>${parseFloat(o.total || '0').toFixed(2)}</span>
                    )}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <Link
                      to={`/workspaces/${wsId}/orders/${o.id}`}
                      className="btn btn-secondary btn-sm"
                    >
                      Details & Action
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Create Order Modal / Drawer */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" style={{ maxWidth: '640px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="card-title">Create Sales Order</h3>
              <button onClick={() => setShowCreateModal(false)} className="btn btn-ghost btn-sm">✕</button>
            </div>

            {createError && (
              <div
                style={{
                  padding: '0.75rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--status-danger-bg)',
                  color: 'var(--status-danger)',
                  fontSize: '0.85rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  marginBottom: '1rem',
                }}
              >
                <AlertCircle size={16} />
                <span>{createError}</span>
              </div>
            )}

            <form onSubmit={handleCreateOrder}>
              <div style={{ marginBottom: '1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <label className="form-label" style={{ margin: 0 }}>Order Items</label>
                  <button type="button" onClick={handleAddItemRow} className="btn btn-ghost btn-sm" style={{ color: 'var(--brand-primary)' }}>
                    + Add Item
                  </button>
                </div>

                {orderItems.map((item, idx) => (
                  <div key={idx} style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '0.65rem' }}>
                    <select
                      className="form-select"
                      style={{ flex: 3 }}
                      value={item.product_id}
                      onChange={(e) => {
                        const updated = [...orderItems];
                        updated[idx].product_id = parseInt(e.target.value, 10);
                        setOrderItems(updated);
                      }}
                      required
                    >
                      {availableProducts.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name} (SKU: {p.sku}) — ${p.price} | Stock: {p.stock_quantity}
                        </option>
                      ))}
                    </select>

                    <input
                      type="number"
                      min="1"
                      className="form-input"
                      style={{ flex: 1, minWidth: '80px' }}
                      value={item.quantity}
                      onChange={(e) => {
                        const updated = [...orderItems];
                        updated[idx].quantity = parseInt(e.target.value, 10) || 1;
                        setOrderItems(updated);
                      }}
                      required
                      placeholder="Qty"
                    />

                    {orderItems.length > 1 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveItemRow(idx)}
                        className="btn btn-ghost btn-sm"
                        style={{ color: 'var(--status-danger)' }}
                      >
                        <Trash2 size={16} />
                      </button>
                    )}
                  </div>
                ))}
              </div>

              <div className="form-group">
                <label className="form-label">Order Notes (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  value={orderNotes}
                  onChange={(e) => setOrderNotes(e.target.value)}
                  placeholder="e.g. Expedited delivery requested by customer"
                />
              </div>

              <div className="modal-footer">
                <button type="button" onClick={() => setShowCreateModal(false)} className="btn btn-secondary" disabled={isSubmitting}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                  {isSubmitting ? 'Creating Order...' : 'Create Draft Order'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
