/**
 * frontend/src/pages/products/ProductCreatePage.tsx
 * Form for creating new products within the workspace.
 */

import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowLeft, PlusCircle, AlertCircle } from 'lucide-react';
import { productsApi } from '../../api/products';
import { extractErrorMessage } from '../../api/client';

export const ProductCreatePage: React.FC = () => {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const wsId = parseInt(workspaceId || '', 10);
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [sku, setSku] = useState('');
  const [description, setDescription] = useState('');
  const [price, setPrice] = useState('19.99');
  const [stockQuantity, setStockQuantity] = useState(0);
  const [lowStockThreshold, setLowStockThreshold] = useState(10);
  const [isActive, setIsActive] = useState(true);

  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isNaN(wsId)) return;

    setError(null);
    setIsSubmitting(true);

    try {
      const created = await productsApi.create(wsId, {
        name: name.trim(),
        sku: sku.trim().toUpperCase(),
        description: description.trim(),
        price: parseFloat(price) || 0,
        stock_quantity: stockQuantity,
        low_stock_threshold: lowStockThreshold,
        is_active: isActive,
      });

      navigate(`/workspaces/${wsId}/products/${created.id}`);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: '640px' }}>
      <div style={{ marginBottom: '1.25rem' }}>
        <Link
          to={`/workspaces/${wsId}/products`}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}
        >
          <ArrowLeft size={16} />
          <span>Back to Product Catalog</span>
        </Link>
      </div>

      <div className="card">
        <div style={{ marginBottom: '1.5rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '1rem' }}>
          <h1 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '0.25rem' }}>Create New Product</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            Define stock attributes, initial inventory, and alert thresholds
          </p>
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
          >
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Product Name *</label>
            <input
              type="text"
              className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Ergonomic Office Chair"
              required
              autoFocus
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">SKU (Stock Keeping Unit) *</label>
              <input
                type="text"
                className="form-input"
                style={{ fontFamily: 'var(--font-mono)' }}
                value={sku}
                onChange={(e) => setSku(e.target.value)}
                placeholder="e.g. CHAIR-001"
                required
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Unique within this workspace
              </span>
            </div>

            <div className="form-group">
              <label className="form-label">Unit Price ($ USD) *</label>
              <input
                type="number"
                step="0.01"
                min="0"
                className="form-input"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                required
              />
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">Initial Stock Quantity</label>
              <input
                type="number"
                min="0"
                className="form-input"
                value={stockQuantity}
                onChange={(e) => setStockQuantity(parseInt(e.target.value, 10) || 0)}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Records restock movement if &gt; 0
              </span>
            </div>

            <div className="form-group">
              <label className="form-label">Low-Stock Alert Threshold</label>
              <input
                type="number"
                min="0"
                className="form-input"
                value={lowStockThreshold}
                onChange={(e) => setLowStockThreshold(parseInt(e.target.value, 10) || 0)}
              />
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Default: 10 units
              </span>
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Description (Optional)</label>
            <textarea
              className="form-textarea"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Product specs, dimensions, or manufacturer reference..."
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', margin: '1rem 0 1.5rem' }}>
            <input
              id="is-active"
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              style={{ width: '16px', height: '16px', cursor: 'pointer' }}
            />
            <label htmlFor="is-active" style={{ fontSize: '0.9rem', cursor: 'pointer' }}>
              Active product (available for sales orders)
            </label>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <Link to={`/workspaces/${wsId}/products`} className="btn btn-secondary">
              Cancel
            </Link>
            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              <PlusCircle size={16} />
              <span>{isSubmitting ? 'Creating Product...' : 'Create Product'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
