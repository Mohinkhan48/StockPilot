/**
 * frontend/src/pages/orders/OrderDetailPage.tsx
 * Order details with immutable snapshot table, server-calculated totals,
 * and lifecycle action triggers (Confirm, Complete, Cancel).
 */

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft,
  CheckCircle,
  PackageCheck,
  Ban,
  Clock,
  AlertCircle,
} from 'lucide-react';
import { ordersApi } from '../../api/orders';
import { Order, OrderStatus } from '../../types';
import { extractErrorMessage } from '../../api/client';
import { CancelOrderModal } from '../../components/orders/CancelOrderModal';

export const OrderDetailPage: React.FC = () => {
  const { workspaceId, orderId } = useParams<{ workspaceId: string; orderId: string }>();
  const wsId = parseInt(workspaceId || '', 10);
  const ordId = parseInt(orderId || '', 10);
  const navigate = useNavigate();

  const [order, setOrder] = useState<Order | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Cancellation modal states
  const [showCancelModal, setShowCancelModal] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);

  const loadOrder = async () => {
    if (isNaN(wsId) || isNaN(ordId)) return;
    setIsLoading(true);
    setError(null);

    try {
      const data = await ordersApi.getDetail(wsId, ordId);
      setOrder(data);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadOrder();
  }, [wsId, ordId]);

  const handleConfirm = async () => {
    if (!window.confirm('Confirm order and atomically deduct warehouse stock for all items?')) return;
    setActionError(null);
    setSuccessMessage(null);
    setIsProcessing(true);
    try {
      await ordersApi.confirm(wsId, ordId);
      setSuccessMessage(`Order #${ordId} confirmed successfully. Warehouse stock deducted and price snapshots locked.`);
      await loadOrder();
    } catch (err) {
      setActionError(extractErrorMessage(err));
    } finally {
      setIsProcessing(false);
    }
  };

  const handleComplete = async () => {
    if (!window.confirm('Mark order as completed? (Goods have left warehouse; terminal state).')) return;
    setActionError(null);
    setSuccessMessage(null);
    setIsProcessing(true);
    try {
      await ordersApi.complete(wsId, ordId);
      setSuccessMessage(`Order #${ordId} marked as completed.`);
      await loadOrder();
    } catch (err) {
      setActionError(extractErrorMessage(err));
    } finally {
      setIsProcessing(false);
    }
  };

  const handleOpenCancelModal = () => {
    setActionError(null);
    setCancelError(null);
    setShowCancelModal(true);
  };

  const handleExecuteCancel = async () => {
    if (isCancelling) return;
    setCancelError(null);
    setIsCancelling(true);
    try {
      await ordersApi.cancel(wsId, ordId);
      setShowCancelModal(false);
      setSuccessMessage(
        order?.status === 'confirmed'
          ? `Order #${ordId} cancelled successfully. Stock has been restored and return movements recorded.`
          : `Order #${ordId} cancelled successfully.`
      );
      await loadOrder();
    } catch (err) {
      setCancelError(extractErrorMessage(err));
    } finally {
      setIsCancelling(false);
    }
  };

  if (isLoading) {
    return <div style={{ padding: '2rem' }}>Loading order details...</div>;
  }

  if (error || !order) {
    return (
      <div className="card" style={{ borderLeft: '4px solid var(--status-danger)' }}>
        <h3 style={{ color: 'var(--status-danger)' }}>Order Not Found</h3>
        <p style={{ margin: '0.5rem 0' }}>{error || 'Unable to retrieve order.'}</p>
        <Link to={`/workspaces/${wsId}/orders`} className="btn btn-secondary btn-sm">
          Return to Orders
        </Link>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: '1.25rem' }}>
        <Link
          to={`/workspaces/${wsId}/orders`}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}
        >
          <ArrowLeft size={16} />
          <span>Back to Orders List</span>
        </Link>
      </div>

      {successMessage && (
        <div
          style={{
            padding: '0.85rem 1.1rem',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--status-success-bg)',
            border: '1px solid var(--status-success-border)',
            color: 'var(--status-success)',
            fontSize: '0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.65rem',
            marginBottom: '1.5rem',
          }}
          role="status"
        >
          <CheckCircle size={18} />
          <span>{successMessage}</span>
        </div>
      )}

      {actionError && (
        <div
          style={{
            padding: '0.85rem 1.1rem',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--status-danger-bg)',
            border: '1px solid var(--status-danger-border)',
            color: 'var(--status-danger)',
            fontSize: '0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.65rem',
            marginBottom: '1.5rem',
          }}
        >
          <AlertCircle size={18} />
          <span>{actionError}</span>
        </div>
      )}

      {/* Header Card with Lifecycle Actions */}
      <div
        className="card"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '1.5rem',
          marginBottom: '2rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.4rem' }}>
            <h1 style={{ fontSize: '1.6rem', fontWeight: 800 }}>Order #{order.id}</h1>
            <span
              className={`badge badge-${order.status}`}
              style={{ fontSize: '0.85rem', padding: '0.35rem 0.75rem' }}
            >
              {order.status.toUpperCase()}
            </span>
          </div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            Created on {new Date(order.created_at).toLocaleString()} by {order.created_by?.username}
          </div>
          {order.notes && (
            <div style={{ marginTop: '0.5rem', fontSize: '0.9rem', color: 'var(--text-primary)' }}>
              Note: <em>{order.notes}</em>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          {order.status === 'pending' && (
            <>
              <button
                onClick={handleConfirm}
                className="btn btn-primary"
                disabled={isProcessing}
              >
                <CheckCircle size={16} />
                <span>Confirm & Lock Stock</span>
              </button>
              <button
                onClick={handleOpenCancelModal}
                className="btn btn-danger"
                disabled={isProcessing}
              >
                <Ban size={16} />
                <span>Cancel Order</span>
              </button>
            </>
          )}

          {order.status === 'confirmed' && (
            <>
              <button
                onClick={handleComplete}
                className="btn btn-primary"
                style={{ backgroundColor: 'var(--status-success)' }}
                disabled={isProcessing}
              >
                <PackageCheck size={16} />
                <span>Mark as Completed</span>
              </button>
              <button
                onClick={handleOpenCancelModal}
                className="btn btn-danger"
                disabled={isProcessing}
              >
                <Ban size={16} />
                <span>Cancel & Restore Stock</span>
              </button>
            </>
          )}

          {(order.status === 'completed' || order.status === 'cancelled') && (
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
              Terminal State — no further state transitions permitted.
            </span>
          )}
        </div>
      </div>

      {/* Line Items Snapshot Table */}
      <div className="card" style={{ marginBottom: '2rem' }}>
        <div className="card-header">
          <h2 className="card-title">
            {order.status === 'pending' ? 'Order Line Items (Pending Draft)' : 'Order Line Items (Immutable Snapshot)'}
          </h2>
          <span style={{ fontSize: '0.85rem', color: order.status === 'pending' ? '#f59e0b' : 'var(--text-muted)' }}>
            {order.status === 'pending' ? 'Prices lock upon confirmation' : 'Prices permanently locked'}
          </span>
        </div>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Item / SKU</th>
                <th>Quantity</th>
                <th>{order.status === 'pending' ? 'Unit Price (Catalog Est.)' : 'Snapshot Unit Price'}</th>
                <th style={{ textAlign: 'right' }}>{order.status === 'pending' ? 'Estimated Line Total' : 'Line Total'}</th>
              </tr>
            </thead>
            <tbody>
              {order.items.map((item) => {
                const displayName = item.product_name || item.live_product_name;
                const displaySku = item.product_sku || item.live_product_sku;
                const isPending = order.status === 'pending';
                const unitPriceDisplay = isPending
                  ? (item.live_product_price != null ? `$${parseFloat(item.live_product_price).toFixed(2)} (Est.)` : 'Pending')
                  : (item.unit_price ? `$${parseFloat(item.unit_price).toFixed(2)}` : 'Pending Confirm');
                const lineTotalDisplay = isPending
                  ? `$${parseFloat(item.estimated_line_total || '0').toFixed(2)}`
                  : `$${parseFloat(item.line_total || '0').toFixed(2)}`;

                return (
                  <tr key={item.id}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{displayName}</div>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        SKU: {displaySku}
                      </div>
                    </td>
                    <td style={{ fontWeight: 600 }}>{item.quantity}</td>
                    <td style={{ color: isPending ? '#f59e0b' : (item.unit_price ? 'var(--text-primary)' : 'var(--text-muted)') }}>
                      {unitPriceDisplay}
                    </td>
                    <td style={{ textAlign: 'right', fontWeight: 700, fontFamily: 'var(--font-mono)', color: isPending ? '#f59e0b' : 'inherit' }}>
                      {lineTotalDisplay}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Server-Computed Total Footer */}
        {order.status === 'pending' ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'flex-end',
              gap: '0.4rem',
              paddingTop: '1.5rem',
              borderTop: '1px solid var(--border-subtle)',
              marginTop: '1.5rem',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <span
                style={{
                  backgroundColor: 'rgba(245, 158, 11, 0.15)',
                  color: '#f59e0b',
                  padding: '0.2rem 0.6rem',
                  borderRadius: '4px',
                  fontSize: '0.75rem',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  border: '1px solid rgba(245, 158, 11, 0.3)',
                }}
              >
                Draft / Pending
              </span>
              <span style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>Estimated Total:</span>
              <span
                style={{
                  fontSize: '1.75rem',
                  fontWeight: 800,
                  fontFamily: 'var(--font-mono)',
                  color: '#f59e0b',
                }}
              >
                ${parseFloat(order.estimated_total || '0').toFixed(2)}
              </span>
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
              Prices lock upon confirmation. (Locked total: ${parseFloat(order.total || '0').toFixed(2)})
            </div>
          </div>
        ) : (
          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              alignItems: 'center',
              gap: '1.5rem',
              paddingTop: '1.5rem',
              borderTop: '1px solid var(--border-subtle)',
              marginTop: '1.5rem',
            }}
          >
            <span style={{ fontSize: '1rem', color: 'var(--text-secondary)' }}>Final Confirmed Total:</span>
            <span
              style={{
                fontSize: '1.75rem',
                fontWeight: 800,
                fontFamily: 'var(--font-mono)',
                color: 'var(--brand-primary)',
              }}
            >
              ${parseFloat(order.total || '0').toFixed(2)}
            </span>
          </div>
        )}
      </div>

      {/* Custom Confirmation Modal */}
      <CancelOrderModal
        isOpen={showCancelModal}
        orderId={order.id}
        orderStatus={order.status}
        itemCount={order.items.length}
        isProcessing={isCancelling}
        error={cancelError}
        onConfirm={handleExecuteCancel}
        onClose={() => {
          if (!isCancelling) setShowCancelModal(false);
        }}
      />
    </div>
  );
};
