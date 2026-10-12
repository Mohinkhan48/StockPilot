/**
 * frontend/src/components/layout/AppLayout.tsx
 * Application layout wrapping Sidebar, Header, and page content.
 */

import React from 'react';
import { Outlet, useParams, Navigate } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { WorkspaceProvider } from '../../context/WorkspaceContext';
import { useAuth } from '../../context/AuthContext';

export const AppLayout: React.FC = () => {
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const { workspaces, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center' }}>
        <span>Loading session...</span>
      </div>
    );
  }

  // If user has no workspaces, redirect to workspace creation
  if (workspaces.length === 0) {
    return <Navigate to="/workspaces" replace />;
  }

  const parsedId = workspaceId ? parseInt(workspaceId, 10) : undefined;

  return (
    <WorkspaceProvider initialWorkspaceId={parsedId}>
      <div style={{ display: 'flex', minHeight: '100vh', width: '100%' }}>
        <Sidebar />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
          <Header />
          <main style={{ flex: 1, padding: '2rem', backgroundColor: 'var(--bg-app)', overflowY: 'auto' }}>
            <Outlet />
          </main>
        </div>
      </div>
    </WorkspaceProvider>
  );
};
