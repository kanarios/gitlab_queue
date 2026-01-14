/**
 * Token storage utilities for localStorage.
 *
 * Design decisions:
 * - Only token is stored (not user data) to minimize localStorage footprint
 * - User data is fetched fresh via /auth/me on each app load
 * - This ensures user data is always current (avatar, name changes)
 */

const TOKEN_KEY = 'gitlab_queue_token';

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    // localStorage may be unavailable (private browsing, etc.)
    return null;
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Silently fail - user will need to re-authenticate on refresh
    console.warn('Failed to persist authentication token');
  }
}

export function clearToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // Silently fail
  }
}

export function hasToken(): boolean {
  return getToken() !== null;
}
