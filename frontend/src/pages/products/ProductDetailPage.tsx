/**
 * frontend/src/pages/products/ProductDetailPage.tsx
 * Product details, restock action, stock adjustment action, and movement ledger.
 */

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft,
  PlusCircle,
  SlidersHorizontal,
  AlertTriangle,
  History,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import { productsApi } from '../../api/products';
import { InventoryMovement, Product } from '../../types';
import { extractErrorMessage } from '../../api/client';

export const ProductDetailPage: React.FC = () => {
  const { workspaceId, productId } = useParams<{ workspaceId: string; productId: string }>();
  const wsId = parseInt(workspaceId || '', 10);
  const prodId = parseInt(productId || '', 10);
  const navigate = useNavigate();

  const [product, setProduct] = useState<Product | null>(null);
  const [movements, setMovements] = useState<InventoryMovement[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [showRestockModal, setShowRestockModal] = useState(false);
  const [restockQty, setRestockQty] = useState(10);
  const [restockNotes, setRestockNotes] = useState('');

  const [showAdjustModal, setShowAdjustModal] = useState(false);
  const [adjustQty, setAdjustQty] = useState(-1);
  const [adjustNotes, setAdjustNotes] = useState('');

  const [actionError, setActionError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadData = async () => {
    if (isNaN(wsId) || isNaN(prodId)) return;
    setIsLoading(true);
    setError(null);

    try {
      const prodData = await productsApi.getDetail(wsId, prodId);
      const moveData = await productsApi.getProductMovements(wsId, prodId);
      setProduct(prodData);
      setMovements(moveData.results);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [wsId, prodId]);

  const handleRestock = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionError(null);
    setIsSubmitting(true);

    try {
      await productsApi.restock(wsId, prodId, { quantity: restockQty, notes: restockNotes });
      setShowRestockModal(false);
      setRestockNotes('');
      await loadData();
    } catch (err) {
      setActionError(extractErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleAdjust = async (e: React.FormEvent) => {
    e.preventDefault();
    setActionError(null);
    setIsSubmitting(true);

    try {
      await productsApi.adjustStock(wsId, prodId, { quantity: adjustQty, notes: adjustNotes });
      setShowAdjustModal(false);
      setAdjustNotes('');
      await loadData();
    } catch (err) {
      setActionError(extractErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleActive = async () => {
    if (!product) return;
    try {
      await productsApi.update(wsId, prodId, { is_active: !product.is_active });
      await loadData();
    } catch (err) {
      setError(extractErrorMessage(err));
    }
  };

  if (isLoading) {
    return <div style={{ padding: '2rem' }}>Loading product details...</div>;
  }

  if (error || !product) {
    return (
      <div className="card" style={{ borderLeft: '4px solid var(--status-danger)' }}>
        <h3 style={{ color: 'var(--status-danger)' }}>Product Not Found</h3>
        <p style={{ margin: '0.5rem 0' }}>{error || 'Unable to retrieve product.'}</p>
        <Link to={`/workspaces/${wsId}/products`} className="btn btn-secondary btn-sm">
          Return to Catalog
        </Link>
      </div>
    );
  }

  return (
    <div>
      {/* Back button */}
      <div style={{ marginBottom: '1.25rem' }}>
        <Link
          to={`/workspaces/${wsId}/products`}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}
        >
          <ArrowLeft size={16} />
          <span>Back to Catalog</span>
        </Link>
      </div>

      {/* Product Summary Header */}
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
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700 }}>{product.name}</h1>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--text-secondary)', background: 'var(--bg-surface-elevated)', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
              {product.sku}
            </span>
            {product.is_low_stock && <span className="badge badge-danger">Low Stock Warning</span>}
            {product.is_active ? <span className="badge badge-success">Active</span> : <span className="badge badge-cancelled">Inactive</span>}
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            {product.description || 'No description provided.'}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button onClick={() => setShowRestockModal(true)} className="btn btn-primary btn-sm">
            <PlusCircle size={15} />
            <span>Restock</span>
          </button>
          <button onClick={() => setShowAdjustModal(true)} className="btn btn-secondary btn-sm">
            <SlidersHorizontal size={15} />
            <span>Adjust Stock</span>
          </button>
          <button onClick={handleToggleActive} className="btn btn-ghost btn-sm">
            {product.is_active ? 'Deactivate' : 'Activate'}
          </button>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
        <div className="card">
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Current Stock Level</span>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: product.is_low_stock ? 'var(--status-danger)' : 'inherit' }}>
            {product.stock_quantity} units
          </div>
        </div>

        <div className="card">
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Low-Stock Threshold</span>
          <div style={{ fontSize: '1.6rem', fontWeight: 700 }}>
            {product.low_stock_threshold} units
          </div>
        </div>

        <div className="card">
          <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Unit Price</span>
          <div style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--brand-primary)' }}>
            ${parseFloat(product.price).toFixed(2)}
          </div>
        </div>
      </div>

      {/* Product-Specific Movement Audit Ledger */}
      <div className="card">
        <div className="card-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <History size={18} color="var(--brand-primary)" />
            <h2 className="card-title">Stock Movement History (Audit Ledger)</h2>
          </div>
        </div>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Date / Time</th>
                <th>Movement Type</th>
                <th>Delta</th>
                <th>Resulting Stock</th>
                <th>Reason / Reference Note</th>
                <th>Recorded By</th>
              </tr>
            </thead>
            <tbody>
              {movements.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    No stock movements recorded for this item yet.
                  </td>
                </tr>
              ) : (
                movements.map((m) => (
                  <tr key={m.id}>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                      {new Date(m.created_at).toLocaleString()}
                    </td>
                    <td>
                      <span className="badge" style={{ textTransform: 'uppercase' }}>
                        {m.movement_type}
                      </span>
                    </td>
                    <td style={{ fontWeight: 700, color: m.quantity >= 0 ? 'var(--status-success)' : 'var(--status-danger)' }}>
                      {m.quantity >= 0 ? `+${m.quantity}` : m.quantity}
                    </td>
                    <td style={{ fontWeight: 600 }}>{m.resulting_stock}</td>
                    <td>{m.notes || '—'}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{m.created_by?.username || 'System'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal: Quick Restock */}
      {showRestockModal && (
        <div className="modal-overlay" onClick={() => setShowRestockModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="card-title">Restock Product: {product.name}</h3>
              <button onClick={() => setShowRestockModal(false)} className="btn btn-ghost btn-sm">✕</button>
            </div>

            {actionError && (
              <div style={{ color: 'var(--status-danger)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                {actionError}
              </div>
            )}

            <form onSubmit={handleRestock}>
              <div className="form-group">
                <label className="form-label">Units to Add (Positive Integer)</label>
                <input
                  type="number"
                  min="1"
                  className="form-input"
                  value={restockQty}
                  onChange={(e) => setRestockQty(parseInt(e.target.value, 10))}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Delivery Note / PO Number (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  value={restockNotes}
                  onChange={(e) => setRestockNotes(e.target.value)}
                  placeholder="e.g. PO-8921 supplier delivery"
                />
              </div>

              <div className="modal-footer">
                <button type="button" onClick={() => setShowRestockModal(false)} className="btn btn-secondary" disabled={isSubmitting}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                  {isSubmitting ? 'Restocking...' : 'Confirm Restock'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Stock Adjustment */}
      {showAdjustModal && (
        <div className="modal-overlay" onClick={() => setShowAdjustModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="card-title">Manual Stock Adjustment</h3>
              <button onClick={() => setShowAdjustModal(false)} className="btn btn-ghost btn-sm">✕</button>
            </div>

            {actionError && (
              <div style={{ color: 'var(--status-danger)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                {actionError}
              </div>
            )}

            <form onSubmit={handleAdjust}>
              <div className="form-group">
                <label className="form-label">Quantity Delta (Positive to Add, Negative to Deduct)</label>
                <input
                  type="number"
                  className="form-input"
                  value={adjustQty}
                  onChange={(e) => setAdjustQty(parseInt(e.target.value, 10))}
                  required
                />
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  Current stock: {product.stock_quantity}. Resulting: {product.stock_quantity + (adjustQty || 0)}
                </span>
              </div>

              <div className="form-group">
                <label className="form-label">Adjustment Reason (Mandatory)</label>
                <input
                  type="text"
                  className="form-input"
                  value={adjustNotes}
                  onChange={(e) => setAdjustNotes(e.target.value)}
                  placeholder="e.g. Broken packaging write-off, Cycle count correction"
                  required
                />
              </div>

              <div className="modal-footer">
                <button type="button" onClick={() => setShowAdjustModal(false)} className="btn btn-secondary" disabled={isSubmitting}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
                  {isSubmitting ? 'Adjusting...' : 'Save Adjustment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
