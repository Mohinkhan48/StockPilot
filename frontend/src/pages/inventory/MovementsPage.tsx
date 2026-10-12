/**
 * frontend/src/pages/inventory/MovementsPage.tsx
 * Full workspace inventory movements audit ledger with filters.
 */

import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeftRight, Filter, ShoppingBag } from 'lucide-react';
import { productsApi } from '../../api/products';
import { InventoryMovement, MovementType } from '../../types';
import { extractErrorMessage } from '../../api/client';

export const MovementsPage: React.FC = () => {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const wsId = parseInt(workspaceId || '', 10);

  const [movements, setMovements] = useState<InventoryMovement[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [movementFilter, setMovementFilter] = useState<string>('all');
  const [page, setPage] = useState<number>(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMovements = async () => {
    if (isNaN(wsId)) return;
    setIsLoading(true);
    setError(null);

    try {
      const params: any = { page };
      if (movementFilter !== 'all') {
        params.movement_type = movementFilter;
      }

      const data = await productsApi.getWorkspaceMovements(wsId, params);
      setMovements(data.results);
      setTotalCount(data.count);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchMovements();
  }, [wsId, page, movementFilter]);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>Stock Movement History</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Append-only audit trail of warehouse restocks, sales deductions, adjustments, and order returns
          </p>
        </div>
      </div>

      {/* Filter Tabs */}
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
            { id: 'all', label: 'All Movements' },
            { id: 'restock', label: 'Restocks' },
            { id: 'sale', label: 'Sales Orders' },
            { id: 'adjustment', label: 'Manual Adjustments' },
            { id: 'return', label: 'Order Returns' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => {
                setMovementFilter(tab.id);
                setPage(1);
              }}
              className={`btn btn-sm ${movementFilter === tab.id ? 'btn-primary' : 'btn-ghost'}`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          {totalCount} total entries in ledger
        </span>
      </div>

      {error && (
        <div className="card" style={{ borderLeft: '4px solid var(--status-danger)', marginBottom: '1.5rem' }}>
          <p style={{ color: 'var(--status-danger)' }}>{error}</p>
        </div>
      )}

      {/* Movements Table */}
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Product SKU</th>
              <th>Product Name</th>
              <th>Type</th>
              <th>Quantity Delta</th>
              <th>Post-Stock Snapshot</th>
              <th>Notes / Reason</th>
              <th>Linked Order</th>
              <th>Actor</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={9} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                  Loading movements ledger...
                </td>
              </tr>
            ) : movements.length === 0 ? (
              <tr>
                <td colSpan={9} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                  No movement records found matching criteria.
                </td>
              </tr>
            ) : (
              movements.map((m) => (
                <tr key={m.id}>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', whiteSpace: 'nowrap' }}>
                    {new Date(m.created_at).toLocaleString()}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{m.product_sku}</td>
                  <td style={{ fontWeight: 500 }}>
                    <Link
                      to={`/workspaces/${wsId}/products/${m.product}`}
                      style={{ color: 'var(--brand-primary)' }}
                    >
                      {m.product_name}
                    </Link>
                  </td>
                  <td>
                    <span className="badge" style={{ textTransform: 'uppercase' }}>
                      {m.movement_type}
                    </span>
                  </td>
                  <td
                    style={{
                      fontWeight: 700,
                      color: m.quantity >= 0 ? 'var(--status-success)' : 'var(--status-danger)',
                    }}
                  >
                    {m.quantity >= 0 ? `+${m.quantity}` : m.quantity}
                  </td>
                  <td style={{ fontWeight: 600 }}>{m.resulting_stock}</td>
                  <td style={{ color: 'var(--text-secondary)' }}>{m.notes || '—'}</td>
                  <td>
                    {m.order ? (
                      <Link
                        to={`/workspaces/${wsId}/orders/${m.order}`}
                        style={{ color: 'var(--brand-primary)', fontWeight: 600 }}
                      >
                        Order #{m.order}
                      </Link>
                    ) : (
                      <span style={{ color: 'var(--text-muted)' }}>—</span>
                    )}
                  </td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                    {m.created_by?.username || 'System'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '1rem', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
        <span>Page {page}</span>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            className="btn btn-secondary btn-sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </button>
          <button
            className="btn btn-secondary btn-sm"
            disabled={movements.length < 20}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
};
