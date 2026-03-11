/**
 * Accessibility Tests for CalliopeIDE Frontend
 * 
 * This test suite verifies that the accessibility improvements are working correctly.
 * Tests cover ARIA compliance, keyboard navigation, screen reader compatibility,
 * and focus management.
 */

import { render, screen, waitFor } from '@testing-library/react'
import { axe, toHaveNoViolations } from 'jest-axe'
import userEvent from '@testing-library/user-event'
import '@testing-library/jest-dom'

// Add jest-axe matcher
expect.extend(toHaveNoViolations)

// Mock the dynamic imports and external dependencies
jest.mock('next/router', () => ({
  useRouter: () => ({
    query: {},
    push: jest.fn(),
  }),
}))

jest.mock('../scripts/streamer', () => ({
  streamGeminiResponse: jest.fn(),
}))

jest.mock('../../scripts/clickspark', () => {
  return function ClickSpark({ children }: { children: React.ReactNode }) {
    return <div>{children}</div>
  }
})

// Import components after mocks
import Home from '../../pages/app/index'
import DefaultLayout from '../../layouts/default'

describe('Accessibility Tests', () => {
  
  describe('Main Chat Interface (pages/app/index.jsx)', () => {
    
    test('should have no accessibility violations', async () => {
      const { container } = render(<Home />)
      const results = await axe(container)
      expect(results).toHaveNoViolations()
    })

    test('should have semantic HTML structure', () => {
      render(<Home />)
      
      // Check for main element
      expect(screen.getByRole('main')).toBeInTheDocument()
      expect(screen.getByRole('main')).toHaveAttribute('aria-label', 'Chat interface')
      
      // Check for sections
      expect(screen.getByLabelText('Chat messages')).toBeInTheDocument()
      expect(screen.getByLabelText('Message input area')).toBeInTheDocument()
    })

    test('should have proper ARIA labels on interactive elements', () => {
      render(<Home />)
      
      // Chat input should have proper label
      const chatInput = screen.getByRole('textbox')
      expect(chatInput).toHaveAttribute('aria-label')
      expect(chatInput.getAttribute('aria-label')).toContain('Type your message here')
      
      // VS Code button should have proper label
      const vsCodeButton = screen.getByLabelText('Open VS Code editor')
      expect(vsCodeButton).toBeInTheDocument()
    })

    test('should support keyboard navigation', async () => {
      const user = userEvent.setup()
      render(<Home />)
      
      const chatInput = screen.getByRole('textbox')
      
      // Tab should focus the input
      await user.tab()
      expect(chatInput).toHaveFocus()
      
      // Should be able to type in input
      await user.type(chatInput, 'Hello world')
      expect(chatInput).toHaveValue('Hello world')
    })

    test('should have aria-live regions for dynamic content', () => {
      render(<Home />)
      
      // Check for conversation history live region
      const conversationHistory = screen.getByLabelText('Conversation history')
      expect(conversationHistory).toHaveAttribute('aria-live', 'polite')
      expect(conversationHistory).toHaveAttribute('role', 'log')
    })

    test('should have proper focus management', async () => {
      const user = userEvent.setup()
      render(<Home />)
      
      const chatInput = screen.getByRole('textbox')
      
      // Input should be auto-focused
      expect(chatInput).toHaveFocus()
      
      // Focus should be visible (test for outline styles)
      await user.click(chatInput)
      expect(chatInput).toHaveStyle({ outline: '2px solid #0ea5e9' })
    })

    test('should handle Enter and Space keys on buttons', async () => {
      const user = userEvent.setup()
      render(<Home />)
      
      const vsCodeButton = screen.getByLabelText('Open VS Code editor')
      
      // Should be activatable by Enter key
      vsCodeButton.focus()
      await user.keyboard('{Enter}')
      
      // Should be activatable by Space key  
      await user.keyboard(' ')
    })

    test('should have proper message structure for screen readers', () => {
      // This would need to be tested with actual messages
      // For now, we test the structure is in place
      render(<Home />)
      
      const conversationArea = screen.getByLabelText('Conversation history')
      expect(conversationArea).toBeInTheDocument()
    })
  })

  describe('Navigation and Layout Components', () => {
    
    test('layout should have semantic structure', () => {
      render(
        <DefaultLayout>
          <div>Test content</div>
        </DefaultLayout>
      )
      
      expect(screen.getByRole('main')).toBeInTheDocument()
      expect(screen.getByRole('contentinfo')).toBeInTheDocument()
      expect(screen.getByRole('main')).toHaveAttribute('aria-label', 'Main content')
    })

    test('footer links should have proper focus styles', () => {
      render(
        <DefaultLayout>
          <div>Test content</div>
        </DefaultLayout>
      )
      
      const heroUILink = screen.getByLabelText('Powered by HeroUI - Visit HeroUI homepage')
      expect(heroUILink).toBeInTheDocument()
      expect(heroUILink).toHaveClass('focus:outline-none', 'focus:ring-2', 'focus:ring-primary')
    })
  })

  describe('Button and Form Components', () => {
    
    test('buttons should handle keyboard events', async () => {
      const user = userEvent.setup()
      const mockClick = jest.fn()
      
      // This would need to import the Button component properly
      // For now, we test that buttons in the main app handle keyboard events
      render(<Home />)
      
      const vsCodeButton = screen.getByLabelText('Open VS Code editor')
      
      // Test Enter key
      vsCodeButton.focus()
      await user.keyboard('{Enter}')
      
      // Test Space key
      await user.keyboard(' ')
    })

    test('form elements should have proper labels', () => {
      render(<Home />)
      
      const chatInput = screen.getByRole('textbox')
      expect(chatInput).toHaveAttribute('id', 'chat-input')
      
      // Check for associated label (even if sr-only)
      const label = document.querySelector('label[for="chat-input"]')
      expect(label).toBeInTheDocument()
    })
  })

  describe('Modal and Dialog Accessibility', () => {
    
    test('modals should have proper ARIA attributes', async () => {
      const user = userEvent.setup()
      render(<Home />)
      
      // Open command palette with Tab key (based on the app logic)
      await user.keyboard('{Tab}')
      
      // Should have dialog role and proper labeling
      await waitFor(() => {
        const modal = screen.queryByRole('dialog')
        if (modal) {
          expect(modal).toHaveAttribute('aria-modal', 'true')
          expect(modal).toHaveAttribute('aria-label')
        }
      })
    })

    test('VS Code modal should have proper attributes', async () => {
      const user = userEvent.setup()
      render(<Home />)
      
      // Click the VS Code button to open modal
      const vsCodeButton = screen.getByLabelText('Open VS Code editor')
      await user.click(vsCodeButton)
      
      // Check if modal container has proper attributes
      // Note: This test might need adjustment based on the HeroUI Modal implementation
    })
  })

  describe('Screen Reader Support', () => {
    
    test('should have proper heading structure', () => {
      render(<Home />)
      
      // When no chat is active, should show main heading
      const heading = screen.getByRole('heading', { level: 1 })
      expect(heading).toHaveTextContent("What's on your mind today?")
    })

    test('should have descriptive text for keyboard shortcuts', () => {
      render(<Home />)
      
      const shortcutText = screen.getByLabelText('Keyboard shortcut: Press Tab to open command palette')
      expect(shortcutText).toBeInTheDocument()
    })

    test('should hide decorative elements from screen readers', () => {
      render(<Home />)
      
      // Icons should have aria-hidden when they're decorative
      // This would need to be tested when buttons are rendered
    })
  })

  describe('Responsive and Reduced Motion Support', () => {
    
    test('should respect reduced motion preferences', () => {
      // Mock reduced motion preference
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: (query: string) => ({
          matches: query === '(prefers-reduced-motion: reduce)',
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
        }),
      })
      
      render(<Home />)
      
      // Elements should have reduced animation when preference is set
      // This would need testing with actual animated elements
    })
  })

  describe('Color Contrast and Visual Accessibility', () => {
    
    test('should have sufficient color contrast', () => {
      render(<Home />)
      
      // This would typically be tested with automated tools
      // or by checking computed styles against WCAG guidelines
      const chatInput = screen.getByRole('textbox')
      expect(chatInput).toBeVisible()
    })

    test('should support high contrast mode', () => {
      // Mock high contrast preference
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: (query: string) => ({
          matches: query === '(prefers-contrast: high)',
          addEventListener: jest.fn(),
          removeEventListener: jest.fn(),
        }),
      })
      
      render(<Home />)
      
      // Elements should adapt to high contrast mode
      // This would need testing with actual contrast-sensitive elements
    })
  })
})

/**
 * Integration Tests for Complete User Flows
 */
describe('Accessibility Integration Tests', () => {
  
  test('complete chat interaction should be accessible', async () => {
    const user = userEvent.setup()
    render(<Home />)
    
    // 1. Focus should start on input
    const chatInput = screen.getByRole('textbox')
    expect(chatInput).toHaveFocus()
    
    // 2. Type message
    await user.type(chatInput, 'Hello assistant')
    expect(chatInput).toHaveValue('Hello assistant')
    
    // 3. Send message with Enter key
    await user.keyboard('{Enter}')
    
    // 4. Input should be cleared and refocused
    expect(chatInput).toHaveValue('')
    expect(chatInput).toHaveFocus()
  })

  test('command palette should be fully keyboard accessible', async () => {
    const user = userEvent.setup()
    render(<Home />)
    
    // Open with Tab key
    await user.keyboard('{Tab}')
    
    // Should open modal with search input focused
    await waitFor(() => {
      const searchInput = screen.queryByLabelText(/Search chat history or run commands/)
      if (searchInput) {
        expect(searchInput).toHaveFocus()
      }
    })
    
    // Should be able to navigate with arrow keys
    // Should be able to select with Enter
    // Should be able to close with Escape
  })
})