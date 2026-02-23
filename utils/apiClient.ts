import { useState } from 'react';

/**
 * Centralized API client with error handling, loading states, and standardized responses
 */

export interface ApiResponse<T = any> {
  data?: T;
  error?: string;
  success: boolean;
  status?: number;
}

export interface ApiRequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  headers?: Record<string, string>;
  body?: any;
  timeout?: number;
}

class ApiClient {
  private baseURL: string = '';

  /**
   * Set the base URL for API calls
   */
  setBaseURL(url: string) {
    this.baseURL = url;
  }

  /**
   * Make an API request with standardized error handling
   */
  async request<T = any>(
    endpoint: string,
    options: ApiRequestOptions = {}
  ): Promise<ApiResponse<T>> {
    const {
      method = 'GET',
      headers = {},
      body,
      timeout = 10000
    } = options;

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      const url = endpoint.startsWith('http') ? endpoint : `${this.baseURL}${endpoint}`;
      
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          ...headers
        },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        return this.handleErrorResponse(response);
      }

      const data = await response.json();
      return {
        data,
        success: true,
        status: response.status
      };

    } catch (error) {
      return this.handleRequestError(error);
    }
  }

  /**
   * GET request
   */
  async get<T = any>(endpoint: string, options?: Omit<ApiRequestOptions, 'method' | 'body'>): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { ...options, method: 'GET' });
  }

  /**
   * POST request
   */
  async post<T = any>(endpoint: string, body?: any, options?: Omit<ApiRequestOptions, 'method' | 'body'>): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { ...options, method: 'POST', body });
  }

  /**
   * PUT request
   */
  async put<T = any>(endpoint: string, body?: any, options?: Omit<ApiRequestOptions, 'method' | 'body'>): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { ...options, method: 'PUT', body });
  }

  /**
   * DELETE request
   */
  async delete<T = any>(endpoint: string, options?: Omit<ApiRequestOptions, 'method' | 'body'>): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { ...options, method: 'DELETE' });
  }

  /**
   * Handle HTTP error responses
   */
  private async handleErrorResponse(response: Response): Promise<ApiResponse> {
    let errorMessage = 'An unexpected error occurred';

    try {
      const errorData = await response.json();
      errorMessage = errorData.message || errorData.error || errorMessage;
    } catch {
      // If we can't parse the error response, use status-based messages
      errorMessage = this.getStatusErrorMessage(response.status);
    }

    return {
      success: false,
      error: errorMessage,
      status: response.status
    };
  }

  /**
   * Handle request-level errors (network, timeout, etc.)
   */
  private handleRequestError(error: any): ApiResponse {
    if (error.name === 'AbortError') {
      return {
        success: false,
        error: 'Request timed out. Please try again.'
      };
    }

    if (!navigator.onLine) {
      return {
        success: false,
        error: 'No internet connection. Please check your network.'
      };
    }

    return {
      success: false,
      error: 'Unable to connect to the server. Please try again.'
    };
  }

  /**
   * Get user-friendly error messages based on HTTP status codes
   */
  private getStatusErrorMessage(status: number): string {
    switch (status) {
      case 400:
        return 'Invalid request. Please check your input.';
      case 401:
        return 'You need to log in to perform this action.';
      case 403:
        return 'You don\'t have permission to perform this action.';
      case 404:
        return 'The requested resource was not found.';
      case 408:
        return 'Request timed out. Please try again.';
      case 429:
        return 'Too many requests. Please wait a moment and try again.';
      case 500:
        return 'Server error. Please try again later.';
      case 502:
        return 'Server temporarily unavailable. Please try again later.';
      case 503:
        return 'Service unavailable. Please try again later.';
      default:
        return 'An unexpected error occurred. Please try again.';
    }
  }
}

// Export a singleton instance
export const apiClient = new ApiClient();

/**
 * Hook for making API calls with loading state
 */
export const useApiCall = <T = any>() => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const makeRequest = async (
    requestFn: () => Promise<ApiResponse<T>>
  ): Promise<T | null> => {
    setLoading(true);
    setError(null);

    try {
      const result = await requestFn();
      
      if (result.success) {
        return result.data || null;
      } else {
        setError(result.error || 'An error occurred');
        return null;
      }
    } catch (err) {
      setError('An unexpected error occurred');
      return null;
    } finally {
      setLoading(false);
    }
  };

  return { makeRequest, loading, error, setError };
};