/**
 * frontend/src/components/orders/CancelOrderModal.tsx
 * Custom confirmation modal for cancelling sales orders and restoring stock.
 */

import React from 'react';
import { AlertTriangle, AlertCircle, RefreshCw, X } from 'lucide-react';
import { OrderStatus } from '../../types';

export interface CancelOrderModalProps {
  isOpen: boolean;
  orderId: number;
  orderStatus: OrderStatus;
  itemCount: number;
  isProcessing: boolean;
  error?: string | null;
  onConfirm: () => void | Promise<void>;
  onClose: () => void;
}

export const CancelOrderModal: React.FC<CancelOrderModalProps> = ({
  isOpen,
  orderId,
  orderStatus,
  itemCount,
  isProcessing,
  error,
  onConfirm,
  onClose,
}) => {
  if (!isOpen) return null;

  const isConfirmed = orderStatus === 'confirmed';

  return (
    <div
      className="modal-overlay"
      onClick={() => {
        if (!isProcessing) onClose();
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="cancel-modal-title"
    >
      <div
        className="modal-content"
        style={{ maxWidth: '520px' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--status-danger-bg)',
                border: '1px solid var(--status-danger-border)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--status-danger)',
                flexShrink: 0,
              }}
            >
              <AlertTriangle size={20} />
            </div>
            <h3 id="cancel-modal-title" className="card-title">
              Cancel Order #{orderId}?
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="btn btn-ghost btn-sm"
            disabled={isProcessing}
            aria-label="Close dialog"
          >
            <X size={18} />
          </button>
        </div>

        {error && (
          <div
            style={{
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--status-danger-bg)',
              border: '1px solid var(--status-danger-border)',
              color: 'var(--status-danger)',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              marginBottom: '1.25rem',
            }}
            role="alert"
          >
            <AlertCircle size={16} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        <div style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.6 }}>
          {isConfirmed ? (
            <p>
              Cancelling this order will restore stock for all{' '}
              <strong style={{ color: 'var(--text-primary)' }}>
                {itemCount} order {itemCount === 1 ? 'item' : 'items'}
              </strong>{' '}
              and record the inventory return in the audit ledger.
            </p>
          ) : (
            <p>
              Are you sure you want to cancel this draft order? No warehouse inventory was deducted for this pending order, so no stock will need to be restored.
            </p>
          )}

          <div
            style={{
              marginTop: '1rem',
              padding: '0.75rem 1rem',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-subtle)',
              fontSize: '0.82rem',
              color: 'var(--text-muted)',
            }}
          >
            {isConfirmed ? (
              <span>
                • Automatic stock replenishment via immutable <code>return</code> movements
                <br />
                • Order status transitions permanently to <code>CANCELLED</code>
              </span>
            ) : (
              <span>
                • Order status transitions permanently to <code>CANCELLED</code>
                <br />
                • Historical draft record preserved
              </span>
            )}
          </div>
        </div>

        <div className="modal-footer">
          <button
            type="button"
            onClick={onClose}
            className="btn btn-secondary"
            disabled={isProcessing}
          >
            Keep Order
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="btn btn-danger"
            disabled={isProcessing}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
          >
            {isProcessing && <RefreshCw size={15} style={{ animation: 'spin 1s linear infinite' }} />}
            <span>{isProcessing ? 'Cancelling Order...' : 'Cancel Order'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
