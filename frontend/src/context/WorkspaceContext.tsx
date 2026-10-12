/**
 * frontend/src/context/WorkspaceContext.tsx
 * Manages active multi-tenant workspace context and role-based permissions.
 */

import React, { createContext, useContext, useEffect, useState, useMemo } from 'react';
import { useAuth } from './AuthContext';
import { Workspace } from '../types';

interface WorkspaceContextType {
  activeWorkspace: Workspace | null;
  activeWorkspaceId: number | null;
  userRole: 'owner' | 'staff' | null;
  isOwner: boolean;
  isStaff: boolean;
  switchWorkspace: (workspaceId: number) => void;
}

const WorkspaceContext = createContext<WorkspaceContextType | undefined>(undefined);

export const WorkspaceProvider: React.FC<{
  children: React.ReactNode;
  initialWorkspaceId?: number;
}> = ({ children, initialWorkspaceId }) => {
  const { workspaces } = useAuth();
  const [activeWorkspaceId, setActiveWorkspaceId] = useState<number | null>(() => {
    if (initialWorkspaceId) return initialWorkspaceId;
    const stored = localStorage.getItem('stockpilot_active_workspace');
    return stored ? parseInt(stored, 10) : null;
  });

  // Keep active workspace in sync with available workspaces
  useEffect(() => {
    if (initialWorkspaceId) {
      setActiveWorkspaceId(initialWorkspaceId);
      localStorage.setItem('stockpilot_active_workspace', initialWorkspaceId.toString());
      return;
    }

    if (workspaces.length > 0) {
      const match = workspaces.find((w) => w.id === activeWorkspaceId);
      if (!match) {
        // Fall back to first available workspace
        const fallback = workspaces[0];
        setActiveWorkspaceId(fallback.id);
        localStorage.setItem('stockpilot_active_workspace', fallback.id.toString());
      }
    } else {
      setActiveWorkspaceId(null);
      localStorage.removeItem('stockpilot_active_workspace');
    }
  }, [workspaces, initialWorkspaceId, activeWorkspaceId]);

  const activeWorkspace = useMemo(() => {
    if (!activeWorkspaceId) return null;
    return workspaces.find((w) => w.id === activeWorkspaceId) || null;
  }, [workspaces, activeWorkspaceId]);

  const userRole = activeWorkspace?.role || null;
  const isOwner = userRole === 'owner';
  const isStaff = userRole === 'staff';

  const switchWorkspace = (workspaceId: number) => {
    setActiveWorkspaceId(workspaceId);
    localStorage.setItem('stockpilot_active_workspace', workspaceId.toString());
  };

  return (
    <WorkspaceContext.Provider
      value={{
        activeWorkspace,
        activeWorkspaceId,
        userRole,
        isOwner,
        isStaff,
        switchWorkspace,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
};

export const useWorkspace = (): WorkspaceContextType => {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error('useWorkspace must be used within a WorkspaceProvider');
  }
  return context;
};
