import type { AuthResponse, User, AuthError, AuthErrorType } from '../types';
import { getToken, setToken, clearToken } from './storage';

const API_BASE = ''; // Vite proxy handles /auth/* routes

/**
 * Redirect to GitLab OAuth login page.
 * The backend handles the OAuth flow initiation.
 */
export function redirectToLogin(): void {
  window.location.href = `${API_BASE}/auth/login`;
}

/**
 * Handle OAuth callback - exchange code for token.
 * Called from AuthCallback page after GitLab redirects back.
 */
export async function handleCallback(
  code: string,
  state: string
): Promise<{ success: true; user: User } | { success: false; error: AuthError }> {
  try {
    const response = await fetch(
      `${API_BASE}/auth/token?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`,
      {
        method: 'POST',
        credentials: 'include', // Include cookies for state validation
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
      return {
        success: false,
        error: mapErrorResponse(response.status, errorData.detail),
      };
    }

    const data: AuthResponse = await response.json();
    setToken(data.access_token);

    return { success: true, user: data.user };
  } catch (error) {
    return {
      success: false,
      error: {
        type: 'network_error',
        message: error instanceof Error ? error.message : 'Network request failed',
      },
    };
  }
}

/**
 * Get current authenticated user.
 * Called on app mount to validate existing token.
 */
export async function getCurrentUser(): Promise<
  { success: true; user: User } | { success: false; error: AuthError }
> {
  const token = getToken();

  if (!token) {
    return {
      success: false,
      error: { type: 'token_expired', message: 'No authentication token' },
    };
  }

  try {
    const response = await fetch(`${API_BASE}/auth/me`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!response.ok) {
      // Clear invalid token
      if (response.status === 401) {
        clearToken();
      }

      const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
      return {
        success: false,
        error: mapErrorResponse(response.status, errorData.detail),
      };
    }

    const user: User = await response.json();
    return { success: true, user };
  } catch (error) {
    return {
      success: false,
      error: {
        type: 'network_error',
        message: error instanceof Error ? error.message : 'Network request failed',
      },
    };
  }
}

/**
 * Logout - clears token locally and notifies backend.
 * Backend logout is stateless (JWT expires naturally).
 */
export async function logout(): Promise<void> {
  const token = getToken();

  // Clear token immediately (optimistic)
  clearToken();

  // Notify backend (fire-and-forget, non-blocking)
  if (token) {
    fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }).catch(() => {
      // Ignore errors - token is already cleared locally
    });
  }
}

/**
 * Get auth header for authenticated API requests.
 * Returns null if no token exists.
 */
export function getAuthHeader(): { Authorization: string } | null {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : null;
}

// Helper: Map HTTP status to AuthErrorType
function mapErrorResponse(status: number, detail: string): AuthError {
  const errorMap: Record<number, AuthErrorType> = {
    400: detail.includes('state') ? 'invalid_state' : 'access_denied',
    401: 'token_expired',
    403: 'no_access',
    502: 'server_error',
    503: 'server_error',
  };

  return {
    type: errorMap[status] || 'server_error',
    message: detail || `Request failed with status ${status}`,
  };
}
