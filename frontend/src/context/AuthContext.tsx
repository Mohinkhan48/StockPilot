/**
 * frontend/src/context/AuthContext.tsx
 * Authentication context managing token, user profile, and user workspaces.
 */

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { authApi } from '../api/auth';
import { User, Workspace } from '../types';

interface AuthContextType {
  token: string | null;
  user: User | null;
  workspaces: Workspace[];
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: { username: string; password: string }) => Promise<void>;
  register: (data: { username: string; email?: string; password: string }) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('stockpilot_token'));
  const [user, setUser] = useState<User | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const refreshUser = useCallback(async () => {
    const currentToken = localStorage.getItem('stockpilot_token');
    if (!currentToken) {
      setUser(null);
      setWorkspaces([]);
      setIsLoading(false);
      return;
    }

    try {
      const data = await authApi.getMe();
      setUser(data.user);
      setWorkspaces(data.workspaces);
    } catch {
      // If fetching user profile fails (e.g. invalid token), reset
      localStorage.removeItem('stockpilot_token');
      setToken(null);
      setUser(null);
      setWorkspaces([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async (credentials: { username: string; password: string }) => {
    const response = await authApi.login(credentials);
    localStorage.setItem('stockpilot_token', response.token);
    setToken(response.token);
    setUser(response.user);
    await refreshUser();
  };

  const register = async (data: { username: string; email?: string; password: string }) => {
    const response = await authApi.register(data);
    localStorage.setItem('stockpilot_token', response.token);
    setToken(response.token);
    setUser(response.user);
    await refreshUser();
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch {
      // Ignore network errors on logout
    } finally {
      localStorage.removeItem('stockpilot_token');
      localStorage.removeItem('stockpilot_active_workspace');
      setToken(null);
      setUser(null);
      setWorkspaces([]);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        workspaces,
        isAuthenticated: !!token && !!user,
        isLoading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
