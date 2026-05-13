import { useState, useCallback } from 'react';
import { API } from '../constants';

interface UseApiOptions {
  baseUrl?: string;
}

interface UseApiReturn {
  loading: boolean;
  error: string | null;
  get: <T>(endpoint: string, params?: Record<string, string>) => Promise<T | null>;
  post: <T>(endpoint: string, body?: unknown) => Promise<T | null>;
  delete: <T>(endpoint: string) => Promise<T | null>;
  clearError: () => void;
}

export function useApi(options: UseApiOptions = {}): UseApiReturn {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const baseUrl = options.baseUrl || API.BASE_URL;

  const get = useCallback(
    async <T>(endpoint: string, params?: Record<string, string>): Promise<T | null> => {
      setLoading(true);
      setError(null);

      try {
        const queryString = params
          ? '?' + new URLSearchParams(params).toString()
          : '';
        const response = await fetch(`${baseUrl}${endpoint}${queryString}`);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        return data as T;
      } catch (err) {
        const message = err instanceof Error ? err.message : '请求失败';
        setError(message);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [baseUrl]
  );

  const post = useCallback(
    async <T>(endpoint: string, body?: unknown): Promise<T | null> => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`${baseUrl}${endpoint}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: body ? JSON.stringify(body) : undefined,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        return data as T;
      } catch (err) {
        const message = err instanceof Error ? err.message : '请求失败';
        setError(message);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [baseUrl]
  );

  const delete_ = useCallback(
    async <T>(endpoint: string): Promise<T | null> => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`${baseUrl}${endpoint}`, {
          method: 'DELETE',
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        return data as T;
      } catch (err) {
        const message = err instanceof Error ? err.message : '请求失败';
        setError(message);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [baseUrl]
  );

  const clearError = useCallback(() => setError(null), []);

  return { loading, error, get, post, delete: delete_, clearError };
}
