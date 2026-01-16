import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import type { User, AuthError } from '../types';
import { getCurrentUser, logout as apiLogout, redirectToLogin } from './api';
import { hasToken, clearToken } from './storage';

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: AuthError | null;
  login: () => void;
  logout: () => Promise<void>;
  setUser: (user: User) => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<AuthError | null>(null);

  // Validate token and fetch user on mount
  useEffect(() => {
    async function validateAuth() {
      // Quick check: no token means no auth
      if (!hasToken()) {
        setIsLoading(false);
        return;
      }

      const result = await getCurrentUser();

      if (result.success) {
        setUser(result.user);
      } else {
        // Token invalid or expired
        clearToken();
        setError(result.error);
      }

      setIsLoading(false);
    }

    validateAuth();
  }, []);

  const login = useCallback(() => {
    redirectToLogin();
  }, []);

  const logout = useCallback(async () => {
    await apiLogout();
    setUser(null);
    setError(null);
  }, []);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const value: AuthContextValue = {
    user,
    isAuthenticated: user !== null,
    isLoading,
    login,
    logout,
    setUser,
    error,
    clearError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
