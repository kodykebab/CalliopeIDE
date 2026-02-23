/**
 * Centralized error handling utility
 */

export interface ErrorInfo {
  message: string;
  code?: string | number;
  details?: any;
}

export enum ErrorType {
  NETWORK = 'NETWORK',
  API = 'API',
  VALIDATION = 'VALIDATION',
  AUTH = 'AUTH',
  TIMEOUT = 'TIMEOUT',
  UNKNOWN = 'UNKNOWN'
}

/**
 * Handle API errors and convert them to user-friendly messages
 */
export const handleApiError = (error: any): ErrorInfo => {
  // Handle fetch/network errors
  if (error instanceof TypeError && error.message.includes('fetch')) {
    return {
      message: 'Unable to connect to the server. Please check your internet connection.',
      code: 'NETWORK_ERROR'
    };
  }

  // Handle abort errors (timeouts)
  if (error.name === 'AbortError') {
    return {
      message: 'Request timed out. Please try again.',
      code: 'TIMEOUT'
    };
  }

  // Handle structured API errors
  if (error.response) {
    const status = error.response.status;
    const data = error.response.data;
    
    return {
      message: getStatusMessage(status, data?.message),
      code: status,
      details: data
    };
  }

  // Handle raw status code errors
  if (typeof error === 'number') {
    return {
      message: getStatusMessage(error),
      code: error
    };
  }

  // Handle string errors
  if (typeof error === 'string') {
    return {
      message: sanitizeErrorMessage(error),
      code: 'UNKNOWN'
    };
  }

  // Handle error objects with message
  if (error.message) {
    return {
      message: sanitizeErrorMessage(error.message),
      code: error.code || 'UNKNOWN'
    };
  }

  // Fallback for unknown errors
  return {
    message: 'An unexpected error occurred. Please try again.',
    code: 'UNKNOWN'
  };
};

/**
 * Get user-friendly message based on HTTP status code
 */
const getStatusMessage = (status: number, customMessage?: string): string => {
  // Use custom message if provided and user-friendly
  if (customMessage && isUserFriendlyMessage(customMessage)) {
    return customMessage;
  }

  switch (status) {
    case 400:
      return 'Invalid request. Please check your input and try again.';
    case 401:
      return 'Authentication required. Please log in to continue.';
    case 403:
      return 'You don\'t have permission to perform this action.';
    case 404:
      return 'The requested resource was not found.';
    case 408:
      return 'Request timed out. Please try again.';
    case 409:
      return 'There was a conflict with your request. Please refresh and try again.';
    case 422:
      return 'Invalid data provided. Please check your input.';
    case 429:
      return 'Too many requests. Please wait a moment and try again.';
    case 500:
      return 'Internal server error. Please try again later.';
    case 502:
      return 'Server temporarily unavailable. Please try again later.';
    case 503:
      return 'Service temporarily unavailable. Please try again later.';
    case 504:
      return 'Request timed out. Please try again.';
    default:
      if (status >= 400 && status < 500) {
        return 'There was an issue with your request. Please try again.';
      }
      if (status >= 500) {
        return 'Server error. Please try again later.';
      }
      return 'An unexpected error occurred. Please try again.';
  }
};

/**
 * Sanitize error messages to avoid exposing technical details
 */
const sanitizeErrorMessage = (message: string): string => {
  // Remove technical stack traces or file paths
  const sanitized = message
    .replace(/at\s+.*\s+\(.*\)/g, '') // Remove stack trace lines
    .replace(/\/[^\s]*\.(js|ts|jsx|tsx)/g, '') // Remove file paths
    .replace(/Error:\s*/i, '') // Remove "Error:" prefix
    .replace(/TypeError:\s*/i, '') // Remove "TypeError:" prefix
    .replace(/ReferenceError:\s*/i, '') // Remove "ReferenceError:" prefix
    .trim();

  // Check if the message is user-friendly
  if (isUserFriendlyMessage(sanitized)) {
    return sanitized;
  }

  // Return generic message for technical errors
  return 'An error occurred. Please try again.';
};

/**
 * Determine if an error message is user-friendly
 */
const isUserFriendlyMessage = (message: string): boolean => {
  const technicalTerms = [
    'undefined', 'null', 'NaN', 'reference',
    'stack', 'trace', 'function', 'object',
    'prototype', 'constructor', 'instanceof',
    'fetch', 'xhr', 'cors', 'preflight',
    'token', 'jwt', 'bearer', 'authorization'
  ];

  const lowerMessage = message.toLowerCase();
  
  // Check if message contains technical terms
  return !technicalTerms.some(term => lowerMessage.includes(term)) &&
         message.length < 200 && // Not too long
         !message.includes('</') && // No HTML
         !message.includes('\\') && // No escape characters
         !/^[A-Z_]+$/.test(message); // Not all caps constant
};

/**
 * Show error notification with consistent styling
 */
export const showErrorNotification = (error: any, options?: {
  title?: string;
  duration?: number;
}) => {
  const errorInfo = handleApiError(error);
  
  // This will be implemented with the toast system
  console.error('Error:', errorInfo);
  
  // For now, return the error info for manual handling
  return errorInfo;
};

/**
 * Handle errors in async operations with loading states
 */
export const withErrorHandling = async <T>(
  asyncFn: () => Promise<T>,
  setLoading?: (loading: boolean) => void,
  setError?: (error: string | null) => void
): Promise<T | null> => {
  try {
    setLoading?.(true);
    setError?.(null);
    
    const result = await asyncFn();
    return result;
  } catch (error) {
    const errorInfo = handleApiError(error);
    setError?.(errorInfo.message);
    return null;
  } finally {
    setLoading?.(false);
  }
};

/**
 * Validate network connectivity
 */
export const checkNetworkConnectivity = (): boolean => {
  return navigator.onLine;
};

/**
 * Get error type based on error characteristics
 */
export const getErrorType = (error: any): ErrorType => {
  if (!navigator.onLine) {
    return ErrorType.NETWORK;
  }
  
  if (error.name === 'AbortError') {
    return ErrorType.TIMEOUT;
  }
  
  if (error.response?.status) {
    const status = error.response.status;
    if (status === 401 || status === 403) {
      return ErrorType.AUTH;
    }
    if (status >= 400 && status < 500) {
      return ErrorType.VALIDATION;
    }
    return ErrorType.API;
  }
  
  return ErrorType.UNKNOWN;
};