/**
 * Centralized error handling utilities for the Calliope IDE
 * Provides standardized error messages and API error handling
 */

export interface ApiError {
  message: string;
  status?: number;
  code?: string;
}

export interface ApiResponse<T = any> {
  data?: T;
  error?: ApiError;
  success: boolean;
}

/**
 * Maps HTTP status codes to user-friendly error messages
 */
const ERROR_MESSAGES: Record<number, string> = {
  400: "Invalid request. Please check your input and try again.",
  401: "Authentication required. Please check your API key.",
  403: "Access denied. You don't have permission for this action.",
  404: "Resource not found. The requested item doesn't exist.",
  408: "Request timeout. Please try again.",
  409: "Conflict. The resource already exists or is being modified.",
  422: "Validation failed. Please check your input data.",
  429: "Too many requests. Please wait a moment before trying again.",
  500: "Server error. Something went wrong on our end.",
  502: "Service temporarily unavailable. Please try again later.",
  503: "Service overloaded. Please try again in a few moments.",
  504: "Request timeout. The service is taking too long to respond.",
};

/**
 * Default fallback error message
 */
const DEFAULT_ERROR_MESSAGE = "An unexpected error occurred. Please try again.";

/**
 * Handles API errors and returns user-friendly messages
 */
export function handleApiError(error: any): ApiError {
  // Handle fetch/network errors
  if (error instanceof TypeError && error.message.includes('fetch')) {
    return {
      message: "Network error. Please check your connection and try again.",
      code: "NETWORK_ERROR"
    };
  }

  // Handle timeout errors
  if (error.name === 'AbortError' || error.message?.includes('timeout')) {
    return {
      message: "Request timeout. Please try again.",
      code: "TIMEOUT_ERROR"
    };
  }

  // Handle HTTP errors with status codes
  if (error.status || error.response?.status) {
    const status = error.status || error.response.status;
    return {
      message: ERROR_MESSAGES[status] || DEFAULT_ERROR_MESSAGE,
      status,
      code: `HTTP_${status}`
    };
  }

  // Handle structured API errors
  if (error.message) {
    // Don't show raw backend error messages to users
    const sensitivePatterns = [
      /stack trace/i,
      /internal server error/i,
      /database/i,
      /sql/i,
      /exception/i,
      /traceback/i
    ];

    const isSensitive = sensitivePatterns.some(pattern => 
      pattern.test(error.message)
    );

    if (isSensitive) {
      return {
        message: DEFAULT_ERROR_MESSAGE,
        code: "INTERNAL_ERROR"
      };
    }

    return {
      message: error.message,
      code: "API_ERROR"
    };
  }

  // Fallback for unknown errors
  return {
    message: DEFAULT_ERROR_MESSAGE,
    code: "UNKNOWN_ERROR"
  };
}

/**
 * Wraps async functions with error handling
 */
export async function safeAsync<T>(
  asyncFn: () => Promise<T>,
  fallback?: T
): Promise<ApiResponse<T>> {
  try {
    const data = await asyncFn();
    return { data, success: true };
  } catch (error) {
    console.error('API Error:', error);
    return {
      error: handleApiError(error),
      success: false,
      data: fallback
    };
  }
}

/**
 * Creates a fetch wrapper with timeout and error handling
 */
export async function safeFetch(
  url: string,
  options: RequestInit = {},
  timeoutMs: number = 10000
): Promise<ApiResponse<any>> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      throw {
        status: response.status,
        message: `HTTP ${response.status}: ${response.statusText}`
      };
    }

    let data;
    const contentType = response.headers.get('content-type');
    
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    return { data, success: true };
  } catch (error) {
    clearTimeout(timeoutId);
    return {
      error: handleApiError(error),
      success: false
    };
  }
}

/**
 * Logs errors for debugging while keeping user messages clean
 */
export function logError(error: any, context?: string) {
  const timestamp = new Date().toISOString();
  console.group(`🚨 Error ${context ? `in ${context}` : ''} - ${timestamp}`);
  console.error('Original error:', error);
  console.error('Stack trace:', error.stack);
  console.groupEnd();
}

/**
 * Validates API response structure
 */
export function validateApiResponse<T>(response: any): ApiResponse<T> {
  if (!response) {
    return {
      error: { message: "No response received from server." },
      success: false
    };
  }

  if (typeof response === 'object' && response.success !== undefined) {
    return response as ApiResponse<T>;
  }

  // Assume successful response if no error structure
  return {
    data: response as T,
    success: true
  };
}