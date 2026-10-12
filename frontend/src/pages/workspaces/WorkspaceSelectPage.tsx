/**
 * frontend/src/pages/workspaces/WorkspaceSelectPage.tsx
 * Workspace selector and workspace creator.
 */

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Building2, Plus, ArrowRight, ShieldCheck, UserCheck, AlertCircle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { workspacesApi } from '../../api/workspaces';
import { extractErrorMessage } from '../../api/client';

export const WorkspaceSelectPage: React.FC = () => {
  const { workspaces, refreshUser } = useAuth();
  const navigate = useNavigate();

  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSelectWorkspace = (workspaceId: number) => {
    localStorage.setItem('stockpilot_active_workspace', workspaceId.toString());
    navigate(`/workspaces/${workspaceId}/dashboard`);
  };

  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newWorkspaceName.trim()) return;

    setError(null);
    setIsCreating(true);

    try {
      const created = await workspacesApi.create({ name: newWorkspaceName.trim() });
      await refreshUser();
      localStorage.setItem('stockpilot_active_workspace', created.id.toString());
      navigate(`/workspaces/${created.id}/dashboard`);
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--bg-app)',
        padding: '2rem',
      }}
    >
      <div style={{ width: '100%', maxWidth: '640px' }}>
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 700, marginBottom: '0.5rem' }}>Select a Workspace</h1>
          <p style={{ color: 'var(--text-secondary)' }}>
            Choose an inventory tenant or create a new organization
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
              marginBottom: '1.5rem',
            }}
          >
            <AlertCircle size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* Existing workspaces list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', marginBottom: '1.75rem' }}>
          {workspaces.map((ws) => (
            <div
              key={ws.id}
              className="card"
              onClick={() => handleSelectWorkspace(ws.id)}
              style={{
                cursor: 'pointer',
                padding: '1.25rem 1.5rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                transition: 'all var(--transition-fast)',
                border: '1px solid var(--border-default)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'var(--brand-primary)';
                e.currentTarget.style.transform = 'translateY(-2px)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = 'var(--border-default)';
                e.currentTarget.style.transform = 'none';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div
                  style={{
                    width: '44px',
                    height: '44px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--brand-primary-light)',
                    color: 'var(--brand-primary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Building2 size={22} />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: 600, marginBottom: '0.2rem' }}>{ws.name}</h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    {ws.role === 'owner' ? <ShieldCheck size={14} color="#10b981" /> : <UserCheck size={14} />}
                    <span>Role: {ws.role === 'owner' ? 'Owner' : 'Staff'}</span>
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--brand-primary)' }}>
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Enter</span>
                <ArrowRight size={18} />
              </div>
            </div>
          ))}

          {workspaces.length === 0 && (
            <div
              className="card"
              style={{ textAlign: 'center', padding: '2.5rem', color: 'var(--text-secondary)' }}
            >
              <Building2 size={36} style={{ margin: '0 auto 1rem', opacity: 0.5 }} />
              <p style={{ marginBottom: '1rem' }}>You do not belong to any workspaces yet.</p>
              <button onClick={() => setShowCreateModal(true)} className="btn btn-primary">
                <Plus size={16} />
                <span>Create Your First Workspace</span>
              </button>
            </div>
          )}
        </div>

        {workspaces.length > 0 && (
          <div style={{ textAlign: 'center' }}>
            <button
              onClick={() => setShowCreateModal(true)}
              className="btn btn-secondary"
              style={{ width: '100%', padding: '0.85rem' }}
            >
              <Plus size={16} />
              <span>Create Another Workspace</span>
            </button>
          </div>
        )}

        {/* Modal for creating a new workspace */}
        {showCreateModal && (
          <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <div className="modal-header">
                <h3 className="card-title">Create Workspace</h3>
                <button onClick={() => setShowCreateModal(false)} className="btn btn-ghost btn-sm">
                  ✕
                </button>
              </div>

              <form onSubmit={handleCreateWorkspace}>
                <div className="form-group">
                  <label className="form-label" htmlFor="ws-name">Workspace / Organization Name</label>
                  <input
                    id="ws-name"
                    type="text"
                    className="form-input"
                    value={newWorkspaceName}
                    onChange={(e) => setNewWorkspaceName(e.target.value)}
                    placeholder="e.g. Acme Warehouse or Central Logistics"
                    required
                    autoFocus
                  />
                </div>

                <div className="modal-footer">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="btn btn-secondary"
                    disabled={isCreating}
                  >
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary" disabled={isCreating}>
                    {isCreating ? 'Creating...' : 'Create & Open'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
