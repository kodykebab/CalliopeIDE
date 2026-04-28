import {
  validateChatInput,
  validateFileName,
  validateContractAddress,
  validateEmail,
  validatePassword,
  validateUrl,
  validateJSON,
  validateFileSize,
  validateFileType,
} from '@/lib/validators'

describe('Validators', () => {
  describe('validateChatInput', () => {
    it('accepts valid chat messages', () => {
      const result = validateChatInput('Hello, world!')
      expect(result.isValid).toBe(true)
      expect(result.error).toBeUndefined()
    })

    it('rejects empty messages', () => {
      const result = validateChatInput('')
      expect(result.isValid).toBe(false)
      expect(result.error).toContain('empty')
    })

    it('rejects whitespace-only messages', () => {
      const result = validateChatInput('   ')
      expect(result.isValid).toBe(false)
    })

    it('respects custom length limits', () => {
      const result = validateChatInput('a', { minLength: 5 })
      expect(result.isValid).toBe(false)
      expect(result.error).toContain('at least 5')
    })

    it('rejects messages exceeding max length', () => {
      const longMessage = 'a'.repeat(10001)
      const result = validateChatInput(longMessage)
      expect(result.isValid).toBe(false)
      expect(result.error).toContain('exceed')
    })
  })

  describe('validateFileName', () => {
    it('accepts valid file names', () => {
      const result = validateFileName('contract.rs')
      expect(result.isValid).toBe(true)
    })

    it('rejects empty file names', () => {
      const result = validateFileName('')
      expect(result.isValid).toBe(false)
    })

    it('rejects file names with invalid characters', () => {
      const invalidNames = ['file<.rs', 'file>.rs', 'file|.rs', 'file*.rs', 'file?.rs']
      invalidNames.forEach(name => {
        const result = validateFileName(name)
        expect(result.isValid).toBe(false)
        expect(result.error).toContain('invalid characters')
      })
    })

    it('rejects excessively long file names', () => {
      const longName = 'a'.repeat(256) + '.rs'
      const result = validateFileName(longName)
      expect(result.isValid).toBe(false)
      expect(result.error).toContain('too long')
    })
  })

  describe('validateContractAddress', () => {
    it('accepts valid Stellar contract addresses', () => {
      const address = 'CAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABSC4'
      const result = validateContractAddress(address)
      expect(result.isValid).toBe(true)
    })

    it('rejects empty addresses', () => {
      const result = validateContractAddress('')
      expect(result.isValid).toBe(false)
    })

    it('rejects addresses not starting with C', () => {
      const result = validateContractAddress('GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABSC4')
      expect(result.isValid).toBe(false)
    })

    it('rejects incorrectly formatted addresses', () => {
      const result = validateContractAddress('C123')
      expect(result.isValid).toBe(false)
      expect(result.error).toContain('Invalid Stellar')
    })
  })

  describe('validateEmail', () => {
    it('accepts valid email addresses', () => {
      const result = validateEmail('user@example.com')
      expect(result.isValid).toBe(true)
    })

    it('rejects empty emails', () => {
      const result = validateEmail('')
      expect(result.isValid).toBe(false)
    })

    it('rejects invalid email formats', () => {
      const invalidEmails = ['user@', '@example.com', 'user example@com', 'user@.com']
      invalidEmails.forEach(email => {
        const result = validateEmail(email)
        expect(result.isValid).toBe(false)
      })
    })

    it('rejects excessively long emails', () => {
      const longEmail = 'a'.repeat(255) + '@example.com'
      const result = validateEmail(longEmail)
      expect(result.isValid).toBe(false)
    })
  })

  describe('validatePassword', () => {
    it('accepts valid passwords', () => {
      const result = validatePassword('SecurePass123!')
      expect(result.isValid).toBe(true)
    })

    it('rejects empty passwords', () => {
      const result = validatePassword('')
      expect(result.isValid).toBe(false)
    })

    it('rejects passwords below minimum length', () => {
      const result = validatePassword('Pass1!', { minLength: 8 })
      expect(result.isValid).toBe(false)
      expect(result.error).toContain('at least 8')
    })

    it('requires uppercase letters when specified', () => {
      const result = validatePassword('securepass123!', { requireUppercase: true })
      expect(result.isValid).toBe(false)
      expect(result.error).toContain('uppercase')
    })

    it('requires numbers when specified', () => {
      const result = validatePassword('SecurePass!', { requireNumber: true })
      expect(result.isValid).toBe(false)
      expect(result.error).toContain('number')
    })

    it('requires special characters when specified', () => {
      const result = validatePassword('SecurePass123', { requireSpecial: true })
      expect(result.isValid).toBe(false)
      expect(result.error).toContain('special character')
    })

    it('accepts passwords with custom rules', () => {
      const result = validatePassword('mypass', {
        minLength: 6,
        requireUppercase: false,
        requireNumber: false,
        requireSpecial: false,
      })
      expect(result.isValid).toBe(true)
    })
  })

  describe('validateUrl', () => {
    it('accepts valid URLs', () => {
      const validUrls = ['https://example.com', 'http://localhost:3000', 'file:///path/to/file']
      validUrls.forEach(url => {
        const result = validateUrl(url)
        expect(result.isValid).toBe(true)
      })
    })

    it('rejects empty URLs', () => {
      const result = validateUrl('')
      expect(result.isValid).toBe(false)
    })

    it('rejects invalid URL formats', () => {
      const result = validateUrl('not a url')
      expect(result.isValid).toBe(false)
    })
  })

  describe('validateJSON', () => {
    it('accepts valid JSON', () => {
      const result = validateJSON('{"key": "value"}')
      expect(result.isValid).toBe(true)
    })

    it('rejects empty JSON', () => {
      const result = validateJSON('')
      expect(result.isValid).toBe(false)
    })

    it('rejects invalid JSON', () => {
      const result = validateJSON('{invalid json}')
      expect(result.isValid).toBe(false)
      expect(result.error).toContain('Invalid JSON')
    })

    it('accepts JSON arrays', () => {
      const result = validateJSON('[1, 2, 3]')
      expect(result.isValid).toBe(true)
    })
  })

  describe('validateFileSize', () => {
    it('accepts files within size limit', () => {
      const result = validateFileSize(5 * 1024 * 1024, 10)
      expect(result.isValid).toBe(true)
    })

    it('rejects files exceeding size limit', () => {
      const result = validateFileSize(15 * 1024 * 1024, 10)
      expect(result.isValid).toBe(false)
      expect(result.error).toContain('too large')
    })

    it('uses default max size of 10MB', () => {
      const result = validateFileSize(11 * 1024 * 1024)
      expect(result.isValid).toBe(false)
    })
  })

  describe('validateFileType', () => {
    it('accepts allowed file types', () => {
      const result = validateFileType('contract.rs', ['rs', 'ts', 'js'])
      expect(result.isValid).toBe(true)
    })

    it('rejects disallowed file types', () => {
      const result = validateFileType('contract.exe', ['rs', 'ts', 'js'])
      expect(result.isValid).toBe(false)
      expect(result.error).toContain('.exe')
    })

    it('rejects files without extension', () => {
      const result = validateFileType('dockerfile', ['rs', 'ts', 'js'])
      expect(result.isValid).toBe(false)
    })

    it('is case-insensitive', () => {
      const result = validateFileType('CONTRACT.RS', ['rs', 'ts', 'js'])
      expect(result.isValid).toBe(true)
    })
  })
})
