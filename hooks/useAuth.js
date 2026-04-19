/**
 * hooks/useAuth.js
 *
 * Centralised auth state + helpers.
 * Wraps localStorage token management, refresh logic, and logout.
 *
 * Usage:
 *   const { user, isLoading, isAuthenticated, logout } = useAuth();
 */

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/router';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:5000';

const TOKEN_KEY   = 'access_token';
const REFRESH_KEY = 'refresh_token';

export function useAuth() {
  const router = useRouter();
  const [user, setUser]           = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // ── helpers ──────────────────────────────────────────────────────────

  function getToken()   { return typeof window !== 'undefined' ? localStorage.getItem(TOKEN_KEY)   : null; }
  function getRefresh() { return typeof window !== 'undefined' ? localStorage.getItem(REFRESH_KEY) : null; }

  function clearTokens() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  }

  // ── fetch current user from /api/auth/me ─────────────────────────────

  const fetchMe = useCallback(async (token) => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.status === 401) {
        // Try refresh
        const newToken = await attemptRefresh();
        if (!newToken) return null;
        const res2 = await fetch(`${BACKEND_URL}/api/auth/me`, {
          headers: { Authorization: `Bearer ${newToken}` },
        });
        if (!res2.ok) return null;
        return (await res2.json()).user ?? null;
      }

      if (!res.ok) return null;
      return (await res.json()).user ?? null;
    } catch {
      return null;
    }
  }, []);

  // ── attempt token refresh ────────────────────────────────────────────

  async function attemptRefresh() {
    const refresh = getRefresh();
    if (!refresh) return null;

    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refresh }),
      });

      if (!res.ok) { clearTokens(); return null; }

      const data = await res.json();
      if (data.access_token) {
        localStorage.setItem(TOKEN_KEY, data.access_token);
        return data.access_token;
      }
      return null;
    } catch {
      return null;
    }
  }

  // ── initialise on mount ───────────────────────────────────────────────

  useEffect(() => {
    async function init() {
      const token = getToken();
      if (!token) { setIsLoading(false); return; }

      const userData = await fetchMe(token);
      setUser(userData);
      setIsLoading(false);
    }
    init();
  }, [fetchMe]);

  // ── logout ────────────────────────────────────────────────────────────

  const logout = useCallback(async () => {
    const token = getToken();
    if (token) {
      try {
        await fetch(`${BACKEND_URL}/api/auth/logout`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch { /* best-effort */ }
    }
    clearTokens();
    setUser(null);
    router.push('/login');
  }, [router]);

  // ── protected-route guard ─────────────────────────────────────────────

  const requireAuth = useCallback(() => {
    if (!isLoading && !user) {
      router.replace('/login');
    }
  }, [isLoading, user, router]);

  return {
    user,
    isLoading,
    isAuthenticated: !!user,
    logout,
    requireAuth,
  };
}