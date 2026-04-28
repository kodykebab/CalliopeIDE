/**
 * Input Validation Utilities for Calliope IDE
 * Provides reusable validation functions for chat input, file names, contract addresses, etc.
 */

export interface ValidationResult {
  isValid: boolean
  error?: string
}

// Chat Input Validation
export function validateChatInput(input: string, options?: { minLength?: number; maxLength?: number }): ValidationResult {
  const { minLength = 1, maxLength = 10000 } = options || {}

  const trimmed = input.trim()

  if (!trimmed) {
    return { isValid: false, error: 'Message cannot be empty' }
  }

  if (trimmed.length < minLength) {
    return { isValid: false, error: `Message must be at least ${minLength} character(s)` }
  }

  if (trimmed.length > maxLength) {
    return { isValid: false, error: `Message cannot exceed ${maxLength} characters` }
  }

  return { isValid: true }
}

// File Name Validation
export function validateFileName(fileName: string): ValidationResult {
  const trimmed = fileName.trim()

  if (!trimmed) {
    return { isValid: false, error: 'File name cannot be empty' }
  }

  if (trimmed.length > 255) {
    return { isValid: false, error: 'File name is too long (max 255 characters)' }
  }

  // Check for invalid characters
  const invalidChars = /[<>:"/\\|?*\x00-\x1f]/g
  if (invalidChars.test(trimmed)) {
    return { isValid: false, error: 'File name contains invalid characters' }
  }

  return { isValid: true }
}

// Contract Address Validation (Stellar)
export function validateContractAddress(address: string): ValidationResult {
  const trimmed = address.trim()

  if (!trimmed) {
    return { isValid: false, error: 'Contract address cannot be empty' }
  }

  // Stellar contract addresses start with 'C' and are 56 characters
  const stellarAddressRegex = /^C[A-Z2-7]{55}$/
  if (!stellarAddressRegex.test(trimmed)) {
    return { isValid: false, error: 'Invalid Stellar contract address format' }
  }

  return { isValid: true }
}

// Email Validation
export function validateEmail(email: string): ValidationResult {
  const trimmed = email.trim().toLowerCase()

  if (!trimmed) {
    return { isValid: false, error: 'Email cannot be empty' }
  }

  // Simple email regex - more comprehensive validation should be done server-side
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(trimmed)) {
    return { isValid: false, error: 'Invalid email address' }
  }

  if (trimmed.length > 254) {
    return { isValid: false, error: 'Email is too long' }
  }

  return { isValid: true }
}

// Password Validation
export interface PasswordValidationOptions {
  minLength?: number
  requireUppercase?: boolean
  requireNumber?: boolean
  requireSpecial?: boolean
}

export function validatePassword(
  password: string,
  options?: PasswordValidationOptions,
): ValidationResult {
  const {
    minLength = 8,
    requireUppercase = true,
    requireNumber = true,
    requireSpecial = true,
  } = options || {}

  if (!password) {
    return { isValid: false, error: 'Password cannot be empty' }
  }

  if (password.length < minLength) {
    return { isValid: false, error: `Password must be at least ${minLength} characters` }
  }

  if (requireUppercase && !/[A-Z]/.test(password)) {
    return { isValid: false, error: 'Password must contain at least one uppercase letter' }
  }

  if (requireNumber && !/\d/.test(password)) {
    return { isValid: false, error: 'Password must contain at least one number' }
  }

  if (requireSpecial && !/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password)) {
    return { isValid: false, error: 'Password must contain at least one special character' }
  }

  return { isValid: true }
}

// URL Validation
export function validateUrl(url: string): ValidationResult {
  const trimmed = url.trim()

  if (!trimmed) {
    return { isValid: false, error: 'URL cannot be empty' }
  }

  try {
    new URL(trimmed)
    return { isValid: true }
  } catch {
    return { isValid: false, error: 'Invalid URL format' }
  }
}

// JSON Validation
export function validateJSON(jsonString: string): ValidationResult {
  const trimmed = jsonString.trim()

  if (!trimmed) {
    return { isValid: false, error: 'JSON cannot be empty' }
  }

  try {
    JSON.parse(trimmed)
    return { isValid: true }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Invalid JSON'
    return { isValid: false, error: `Invalid JSON: ${message}` }
  }
}

// File Size Validation
export function validateFileSize(
  fileSize: number,
  maxSizeMB: number = 10,
): ValidationResult {
  const maxSizeBytes = maxSizeMB * 1024 * 1024

  if (fileSize > maxSizeBytes) {
    return {
      isValid: false,
      error: `File is too large (max ${maxSizeMB}MB, got ${(fileSize / 1024 / 1024).toFixed(2)}MB)`,
    }
  }

  return { isValid: true }
}

// File Type Validation
export function validateFileType(
  fileName: string,
  allowedExtensions: string[],
): ValidationResult {
  const ext = fileName.split('.').pop()?.toLowerCase()

  if (!ext) {
    return { isValid: false, error: 'File must have an extension' }
  }

  if (!allowedExtensions.includes(ext)) {
    return {
      isValid: false,
      error: `File type .${ext} is not allowed. Allowed types: ${allowedExtensions.map(e => `.${e}`).join(', ')}`,
    }
  }

  return { isValid: true }
}
