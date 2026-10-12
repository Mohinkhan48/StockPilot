/**
 * frontend/src/pages/products/ProductListPage.tsx
 * Catalog management: list, search, filter, quick restock, and create product.
 */

import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Package,
  Plus,
  Search,
  AlertTriangle,
  ArrowUpDown,
  Filter,
  CheckCircle,
  XCircle,
} from 'lucide-react';
import { productsApi } from '../../api/products';
import { Product } from '../../types';
import { extractErrorMessage } from '../../api/client';

export const ProductListPage: React.FC = () => {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const wsId = parseInt(workspaceId || '', 10);

  const [products, setProducts] = useState<Product[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterActive, setFilterActive] = useState<string>('all');
  const [filterLowStock, setFilterLowStock] = useState<boolean>(false);
  const [ordering, setOrdering] = useState<string>('name');
  const [page, setPage] = useState<number>(1);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load products
  const fetchProducts = async () => {
    if (isNaN(wsId)) return;
    setIsLoading(true);
    setError(null);

    try {
      const params: any = { page, ordering };
      if (searchTerm.trim()) params.search = searchTerm.trim();
      if (filterActive === 'active') params.is_active = true;
      if (filterActive === 'inactive') params.is_active = false;
      if (filterLowStock) params.low_stock = true;

      const data = await productsApi.list(wsId, params);
      setProducts(data.results);
      setTotalCount(data.count);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts();
  }, [wsId, page, ordering, filterActive, filterLowStock]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchProducts();
  };

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>Product Catalog</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Manage stock keeping units (SKUs), inventory thresholds, and active status
          </p>
        </div>

        <Link to={`/workspaces/${wsId}/products/new`} className="btn btn-primary btn-sm">
          <Plus size={16} />
          <span>Add Product</span>
        </Link>
      </div>

      {/* Filter / Search Bar */}
      <div
        className="card"
        style={{
          padding: '1rem',
          marginBottom: '1.5rem',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '1rem',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '0.5rem', flex: 1, minWidth: '260px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <Search
              size={16}
              style={{ position: 'absolute', left: '0.75rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}
            />
            <input
              type="text"
              className="form-input"
              style={{ paddingLeft: '2.25rem' }}
              placeholder="Search by name, SKU, or description..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-secondary btn-sm">
            Search
          </button>
        </form>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <select
            className="form-select"
            style={{ width: 'auto', padding: '0.5rem 0.75rem' }}
            value={filterActive}
            onChange={(e) => {
              setFilterActive(e.target.value);
              setPage(1);
            }}
          >
            <option value="all">All Statuses</option>
            <option value="active">Active Only</option>
            <option value="inactive">Inactive Only</option>
          </select>

          <button
            type="button"
            className={`btn btn-sm ${filterLowStock ? 'btn-danger' : 'btn-secondary'}`}
            onClick={() => {
              setFilterLowStock(!filterLowStock);
              setPage(1);
            }}
          >
            <AlertTriangle size={14} />
            <span>Low-Stock Filter</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderLeft: '4px solid var(--status-danger)', marginBottom: '1.5rem' }}>
          <p style={{ color: 'var(--status-danger)' }}>{error}</p>
        </div>
      )}

      {/* Products Data Table */}
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>SKU</th>
              <th>Name</th>
              <th>Price</th>
              <th>Stock Level</th>
              <th>Low Threshold</th>
              <th>Status</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                  Loading product catalog...
                </td>
              </tr>
            ) : products.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                  No products found in this workspace.
                </td>
              </tr>
            ) : (
              products.map((p) => (
                <tr key={p.id}>
                  <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{p.sku}</td>
                  <td>
                    <Link
                      to={`/workspaces/${wsId}/products/${p.id}`}
                      style={{ fontWeight: 600, color: 'var(--brand-primary)' }}
                    >
                      {p.name}
                    </Link>
                  </td>
                  <td>${parseFloat(p.price).toFixed(2)}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontWeight: 700 }}>{p.stock_quantity}</span>
                      {p.is_low_stock && (
                        <span className="badge badge-danger" title="At or below low-stock threshold">
                          Low Stock
                        </span>
                      )}
                    </div>
                  </td>
                  <td>{p.low_stock_threshold}</td>
                  <td>
                    {p.is_active ? (
                      <span className="badge badge-success">Active</span>
                    ) : (
                      <span className="badge badge-cancelled">Inactive</span>
                    )}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <Link
                      to={`/workspaces/${wsId}/products/${p.id}`}
                      className="btn btn-secondary btn-sm"
                    >
                      View / Adjust
                    </Link>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination summary */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '1rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
        <span>Total: {totalCount} product(s)</span>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            className="btn btn-secondary btn-sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </button>
          <span style={{ padding: '0.35rem 0.75rem', fontWeight: 600 }}>Page {page}</span>
          <button
            className="btn btn-secondary btn-sm"
            disabled={products.length < 20}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};
