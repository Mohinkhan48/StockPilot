/**
 * frontend/src/api/client.ts
 * Centralized Axios client configured with Token authentication,
 * automatic 401 handling, and DRF error extraction.
 */

import axios, { AxiosError } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: inject DRF Token from localStorage
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('stockpilot_token');
    if (token) {
      config.headers.Authorization = `Token ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: handle 401 Unauthorized globally
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Clear token and notify app
      localStorage.removeItem('stockpilot_token');
      // If not already on auth page, redirect
      if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/register')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

/**
 * Extracts a human-readable string from Django REST Framework error responses.
 */
export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data;
    if (!data) {
      if (error.message === 'Network Error') {
        return 'Unable to connect to the StockPilot backend server (http://127.0.0.1:8000). Please ensure it is running.';
      }
      return error.message || 'An unexpected error occurred.';
    }

    if (typeof data === 'string') {
      return data;
    }

    if (data.detail && typeof data.detail === 'string') {
      return data.detail;
    }

    if (Array.isArray(data.non_field_errors)) {
      return data.non_field_errors.join(' ');
    }

    // Collect all field-specific errors
    const messages: string[] = [];
    for (const [key, val] of Object.entries(data)) {
      if (Array.isArray(val)) {
        messages.push(`${key}: ${val.join(' ')}`);
      } else if (typeof val === 'string') {
        messages.push(`${key}: ${val}`);
      } else if (typeof val === 'object' && val !== null) {
        messages.push(`${key}: ${JSON.stringify(val)}`);
      }
    }

    if (messages.length > 0) {
      return messages.join(' | ');
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return 'An unexpected error occurred.';
}
