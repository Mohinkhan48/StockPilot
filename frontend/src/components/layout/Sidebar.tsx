/**
 * frontend/src/components/layout/Sidebar.tsx
 * Workspace-aware navigation sidebar.
 */

import React from 'react';
import { NavLink, useParams } from 'react-router-dom';
import {
  LayoutDashboard,
  Package,
  ArrowLeftRight,
  ShoppingCart,
  Building2,
  ShieldCheck,
  UserCheck,
} from 'lucide-react';
import { useWorkspace } from '../../context/WorkspaceContext';

export const Sidebar: React.FC = () => {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const { activeWorkspace, userRole } = useWorkspace();

  const basePath = `/workspaces/${workspaceId}`;

  const navItems = [
    {
      to: `${basePath}/dashboard`,
      label: 'Dashboard',
      icon: LayoutDashboard,
    },
    {
      to: `${basePath}/products`,
      label: 'Products',
      icon: Package,
    },
    {
      to: `${basePath}/inventory/movements`,
      label: 'Movement History',
      icon: ArrowLeftRight,
    },
    {
      to: `${basePath}/orders`,
      label: 'Sales Orders',
      icon: ShoppingCart,
    },
  ];

  return (
    <aside
      style={{
        width: '260px',
        backgroundColor: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        position: 'sticky',
        top: 0,
      }}
    >
      {/* Brand logo & active workspace name */}
      <div style={{ padding: '1.5rem', borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', marginBottom: '0.75rem' }}>
          <div
            style={{
              width: '34px',
              height: '34px',
              borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, var(--brand-primary), #818cf8)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ffffff',
              fontWeight: 700,
            }}
          >
            SP
          </div>
          <span style={{ fontSize: '1.2rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
            StockPilot
          </span>
        </div>

        {activeWorkspace && (
          <div
            style={{
              padding: '0.6rem 0.75rem',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
              <Building2 size={16} color="var(--brand-primary)" style={{ flexShrink: 0 }} />
              <span
                style={{
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {activeWorkspace.name}
              </span>
            </div>
            <span
              style={{
                fontSize: '0.7rem',
                padding: '0.15rem 0.45rem',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: userRole === 'owner' ? 'rgba(99, 102, 241, 0.2)' : 'rgba(100, 116, 139, 0.2)',
                color: userRole === 'owner' ? '#818cf8' : '#94a3b8',
                fontWeight: 600,
                textTransform: 'uppercase',
              }}
            >
              {userRole || 'Member'}
            </span>
          </div>
        )}
      </div>

      {/* Navigation links */}
      <nav style={{ padding: '1rem', flex: 1, display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.7rem 0.9rem',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.9rem',
                fontWeight: 500,
                color: isActive ? '#ffffff' : 'var(--text-secondary)',
                backgroundColor: isActive ? 'var(--brand-primary-light)' : 'transparent',
                borderLeft: isActive ? '3px solid var(--brand-primary)' : '3px solid transparent',
                transition: 'all var(--transition-fast)',
              })}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>

      {/* Role info footer */}
      <div
        style={{
          padding: '1rem 1.5rem',
          borderTop: '1px solid var(--border-subtle)',
          fontSize: '0.75rem',
          color: 'var(--text-muted)',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
        }}
      >
        {userRole === 'owner' ? <ShieldCheck size={14} color="#10b981" /> : <UserCheck size={14} color="#94a3b8" />}
        <span>Active permissions: {userRole === 'owner' ? 'Owner (Full Access)' : 'Staff (Operations)'}</span>
      </div>
    </aside>
  );
};
