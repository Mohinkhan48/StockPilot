/**
 * frontend/src/App.tsx
 * Application Router configuration and Root Providers.
 */

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ProtectedRoute } from './components/common/ProtectedRoute';
import { AppLayout } from './components/layout/AppLayout';

import { LoginPage } from './pages/auth/LoginPage';
import { RegisterPage } from './pages/auth/RegisterPage';
import { WorkspaceSelectPage } from './pages/workspaces/WorkspaceSelectPage';
import { DashboardPage } from './pages/dashboard/DashboardPage';
import { ProductListPage } from './pages/products/ProductListPage';
import { ProductCreatePage } from './pages/products/ProductCreatePage';
import { ProductDetailPage } from './pages/products/ProductDetailPage';
import { MovementsPage } from './pages/inventory/MovementsPage';
import { OrderListPage } from './pages/orders/OrderListPage';
import { OrderDetailPage } from './pages/orders/OrderDetailPage';

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public Auth Routes */}
          <Route path="/" element={<LoginPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Workspace Selection & Onboarding */}
          <Route
            path="/workspaces"
            element={
              <ProtectedRoute>
                <WorkspaceSelectPage />
              </ProtectedRoute>
            }
          />

          {/* Workspace-Scoped Authenticated Routes */}
          <Route
            path="/workspaces/:workspaceId"
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            {/* Redirect /workspaces/:id directly to /workspaces/:id/dashboard */}
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="products" element={<ProductListPage />} />
            <Route path="products/new" element={<ProductCreatePage />} />
            <Route path="products/:productId" element={<ProductDetailPage />} />
            <Route path="inventory/movements" element={<MovementsPage />} />
            <Route path="orders" element={<OrderListPage />} />
            <Route path="orders/:orderId" element={<OrderDetailPage />} />
          </Route>

          {/* Fallback Redirect */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
};

export default App;
