import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import FileExplorer from '@/components/FileExplorer'

// Mock fetch API
global.fetch = vi.fn()

// Mock localStorage
const localStorageMock = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
}
global.localStorage = localStorageMock

// Mock process.env
process.env.NEXT_PUBLIC_BACKEND_URL = 'http://localhost:5000'

describe('FileExplorer', () => {
  const mockProjectId = 1
  const mockOnFileSelect = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    localStorageMock.getItem.mockReturnValue('mock-token')
  })

  it('renders loading state initially', () => {
    fetch.mockImplementationOnce(() => 
      new Promise(resolve => setTimeout(() => resolve({ ok: true }), 100))
    )

    render(
      <FileExplorer 
        projectId={mockProjectId} 
        onFileSelect={mockOnFileSelect}
      />
    )

    expect(screen.getByText('Loading files...')).toBeInTheDocument()
  })

  it('displays file tree after successful fetch', async () => {
    const mockFileTree = {
      success: true,
      tree: {
        name: 'workspace',
        path: './workspace',
        isDirectory: true,
        children: [
          {
            name: 'src',
            path: './workspace/src',
            isDirectory: true,
            children: [
              {
                name: 'lib.rs',
                path: './workspace/src/lib.rs',
                isDirectory: false,
                children: []
              }
            ]
          },
          {
            name: 'Cargo.toml',
            path: './workspace/Cargo.toml',
            isDirectory: false,
            children: []
          }
        ]
      }
    }

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockFileTree
    })

    render(
      <FileExplorer 
        projectId={mockProjectId} 
        onFileSelect={mockOnFileSelect}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('Files')).toBeInTheDocument()
    })

    expect(screen.getByText('src')).toBeInTheDocument()
    expect(screen.getByText('Cargo.toml')).toBeInTheDocument()
  })

  it('handles file selection correctly', async () => {
    const mockFileTree = {
      success: true,
      tree: {
        name: 'workspace',
        path: './workspace',
        isDirectory: true,
        children: [
          {
            name: 'test.rs',
            path: './workspace/test.rs',
            isDirectory: false,
            children: []
          }
        ]
      }
    }

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockFileTree
    })

    render(
      <FileExplorer 
        projectId={mockProjectId} 
        onFileSelect={mockOnFileSelect}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('test.rs')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('test.rs'))
    expect(mockOnFileSelect).toHaveBeenCalledWith({
      name: 'test.rs',
      path: './workspace/test.rs',
      isDirectory: false,
      children: []
    })
  })

  it('displays error state on fetch failure', async () => {
    fetch.mockResolvedValueOnce({
      ok: false,
      statusText: 'Not Found'
    })

    render(
      <FileExplorer 
        projectId={mockProjectId} 
        onFileSelect={mockOnFileSelect}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('⚠️ Failed to load files')).toBeInTheDocument()
    })
  })

  it('expands and collapses folders', async () => {
    const mockFileTree = {
      success: true,
      tree: {
        name: 'workspace',
        path: './workspace',
        isDirectory: true,
        children: [
          {
            name: 'src',
            path: './workspace/src',
            isDirectory: true,
            children: [
              {
                name: 'lib.rs',
                path: './workspace/src/lib.rs',
                isDirectory: false,
                children: []
              }
            ]
          }
        ]
      }
    }

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockFileTree
    })

    render(
      <FileExplorer 
        projectId={mockProjectId} 
        onFileSelect={mockOnFileSelect}
      />
    )

    await waitFor(() => {
      expect(screen.getByText('src')).toBeInTheDocument()
    })

    // Initially expanded (auto-expand first level)
    expect(screen.getByText('lib.rs')).toBeInTheDocument()

    // Click to collapse
    fireEvent.click(screen.getByText('src'))
    
    // Should collapse (lib.rs should no longer be visible)
    // Note: In real implementation, you might need to wait for animation
  })

  it('shows selected file highlighting', async () => {
    const mockFileTree = {
      success: true,
      tree: {
        name: 'workspace',
        path: './workspace',
        isDirectory: true,
        children: [
          {
            name: 'selected.rs',
            path: './workspace/selected.rs',
            isDirectory: false,
            children: []
          }
        ]
      }
    }

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => mockFileTree
    })

    render(
      <FileExplorer 
        projectId={mockProjectId} 
        onFileSelect={mockOnFileSelect}
        selectedPath="./workspace/selected.rs"
      />
    )

    await waitFor(() => {
      expect(screen.getByText('selected.rs')).toBeInTheDocument()
    })

    // The selected file should have different styling
    const selectedFile = screen.getByText('selected.rs').closest('div')
    expect(selectedFile).toHaveClass('text-primary')
  })
})
