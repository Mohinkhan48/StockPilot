/**
 * frontend/src/components/layout/Header.tsx
 * Top header with workspace switcher, user details, and logout action.
 */

import React from 'react';
import { useNavigate } from 'react-router-dom';
import { LogOut, ArrowLeftRight, User as UserIcon } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useWorkspace } from '../../context/WorkspaceContext';

export const Header: React.FC = () => {
  const { user, logout, workspaces } = useAuth();
  const { activeWorkspace, switchWorkspace } = useWorkspace();
  const navigate = useNavigate();

  const handleWorkspaceChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newId = parseInt(e.target.value, 10);
    if (!isNaN(newId)) {
      switchWorkspace(newId);
      navigate(`/workspaces/${newId}/dashboard`);
    }
  };

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <header
      style={{
        height: '64px',
        backgroundColor: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 2rem',
        position: 'sticky',
        top: 0,
        zIndex: 20,
      }}
    >
      {/* Workspace Switcher */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Active Tenant:</span>
        <select
          value={activeWorkspace?.id || ''}
          onChange={handleWorkspaceChange}
          style={{
            backgroundColor: 'var(--bg-surface-elevated)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--radius-md)',
            padding: '0.4rem 0.75rem',
            fontSize: '0.85rem',
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          {workspaces.map((ws) => (
            <option key={ws.id} value={ws.id}>
              {ws.name} ({ws.role || 'Member'})
            </option>
          ))}
        </select>

        <button
          onClick={() => navigate('/workspaces')}
          title="Switch or create workspace"
          className="btn btn-ghost btn-sm"
          style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}
        >
          <ArrowLeftRight size={14} />
          <span>Switch / New</span>
        </button>
      </div>

      {/* User profile & logout */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-default)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--brand-primary)',
            }}
          >
            <UserIcon size={16} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>{user?.username}</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{user?.email || 'Authenticated'}</span>
          </div>
        </div>

        <button
          onClick={handleLogout}
          className="btn btn-secondary btn-sm"
          style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
        >
          <LogOut size={14} />
          <span>Logout</span>
        </button>
      </div>
    </header>
  );
};
