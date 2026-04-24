"use client"

import { useState, useEffect } from "react"
import { ChevronRight, ChevronDown, File, Folder, FolderOpen, FileText, FileCode, FileJson, FilePlus } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"

// ── Icon mapping for different file types ─────────────────────────────────────
const getFileIcon = (fileName, isDirectory) => {
  if (isDirectory) {
    return Folder
  }
  
  const ext = fileName.split('.').pop()?.toLowerCase()
  switch (ext) {
    case 'js':
    case 'jsx':
    case 'ts':
    case 'tsx':
      return FileCode
    case 'json':
      return FileJson
    case 'md':
    case 'txt':
      return FileText
    default:
      return File
  }
}

// ── File tree node component ─────────────────────────────────────────────────
const FileTreeNode = ({ 
  node, 
  level = 0, 
  onFileSelect, 
  selectedPath, 
  expandedNodes, 
  onToggleExpand 
}) => {
  const isExpanded = expandedNodes.includes(node.path)
  const isSelected = selectedPath === node.path
  const Icon = isExpanded ? FolderOpen : Folder
  const FileIcon = getFileIcon(node.name, node.isDirectory)

  const handleClick = () => {
    if (node.isDirectory) {
      onToggleExpand(node.path)
    } else {
      onFileSelect(node)
    }
  }

  return (
    <div>
      <motion.div
        className={`
          flex items-center gap-1 px-2 py-1 rounded cursor-pointer
          hover:bg-accent/50 transition-colors duration-150
          ${isSelected ? 'bg-primary/20 text-primary' : ''}
        `}
        style={{ paddingLeft: `${level * 12 + 8}px` }}
        onClick={handleClick}
        whileHover={{ x: 2 }}
        whileTap={{ scale: 0.98 }}
      >
        {node.isDirectory && (
          <motion.div
            animate={{ rotate: isExpanded ? 90 : 0 }}
            transition={{ duration: 0.2 }}
          >
            <ChevronRight size={12} />
          </motion.div>
        )}
        
        <motion.div
          animate={{ scale: isSelected ? 1.1 : 1 }}
          transition={{ duration: 0.2 }}
        >
          {node.isDirectory ? (
            <Icon size={16} className="text-blue-500" />
          ) : (
            <FileIcon size={16} className="text-gray-500" />
          )}
        </motion.div>
        
        <span className="text-sm truncate select-none">
          {node.name}
        </span>
      </motion.div>
      
      <AnimatePresence>
        {isExpanded && node.children && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {node.children.map((child) => (
              <FileTreeNode
                key={child.path}
                node={child}
                level={level + 1}
                onFileSelect={onFileSelect}
                selectedPath={selectedPath}
                expandedNodes={expandedNodes}
                onToggleExpand={onToggleExpand}
              />
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

// ── Main FileExplorer component ─────────────────────────────────────────────
export default function FileExplorer({ 
  projectId, 
  onFileSelect, 
  selectedPath, 
  className = "" 
}) {
  const [fileTree, setFileTree] = useState(null)
  const [expandedNodes, setExpandedNodes] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // ── Fetch file tree from backend ───────────────────────────────────────
  const fetchFileTree = async () => {
    if (!projectId) return

    setLoading(true)
    setError(null)
    
    try {
      const token = localStorage.getItem('access_token')
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000"
      const response = await fetch(`${backendUrl}/api/projects/${projectId}/files`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (!response.ok) {
        throw new Error(`Failed to fetch file tree: ${response.statusText}`)
      }

      const data = await response.json()
      if (data.success) {
        setFileTree(data.tree)
        // Auto-expand first level
        if (data.tree?.children) {
          setExpandedNodes(data.tree.children.map(child => child.path))
        }
      } else {
        throw new Error(data.error || 'Unknown error')
      }
    } catch (err) {
      setError(err.message)
      console.error('Error fetching file tree:', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchFileTree()
  }, [projectId])

  // ── Toggle folder expansion ─────────────────────────────────────────────
  const toggleExpand = (path) => {
    setExpandedNodes(prev => 
      prev.includes(path) 
        ? prev.filter(p => p !== path)
        : [...prev, path]
    )
  }

  // ── Handle file selection ───────────────────────────────────────────────
  const handleFileSelect = (node) => {
    if (!node.isDirectory) {
      onFileSelect(node)
    }
  }

  // ── Refresh file tree ───────────────────────────────────────────────────
  const refreshTree = () => {
    fetchFileTree()
  }

  if (loading) {
    return (
      <div className={`p-4 text-center text-muted-foreground ${className}`}>
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary mx-auto mb-2"></div>
        Loading files...
      </div>
    )
  }

  if (error) {
    return (
      <div className={`p-4 text-center text-destructive ${className}`}>
        <div className="mb-2">⚠️ Failed to load files</div>
        <div className="text-xs text-muted-foreground mb-2">{error}</div>
        <button 
          onClick={refreshTree}
          className="text-xs text-primary hover:underline"
        >
          Retry
        </button>
      </div>
    )
  }

  if (!fileTree) {
    return (
      <div className={`p-4 text-center text-muted-foreground ${className}`}>
        No files to display
      </div>
    )
  }

  return (
    <div className={`h-full flex flex-col ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-3 border-b border-border">
        <h3 className="text-sm font-semibold text-foreground">Files</h3>
        <button
          onClick={refreshTree}
          className="p-1 rounded hover:bg-accent/50 transition-colors"
          title="Refresh files"
        >
          <motion.div
            animate={{ rotate: loading ? 360 : 0 }}
            transition={{ duration: 0.5, ease: "linear" }}
          >
            <FilePlus size={14} className="text-muted-foreground" />
          </motion.div>
        </button>
      </div>

      {/* File tree */}
      <div className="flex-1 overflow-y-auto">
        {fileTree.children && fileTree.children.length > 0 ? (
          fileTree.children.map((node) => (
            <FileTreeNode
              key={node.path}
              node={node}
              onFileSelect={handleFileSelect}
              selectedPath={selectedPath}
              expandedNodes={expandedNodes}
              onToggleExpand={toggleExpand}
            />
          ))
        ) : (
          <div className="p-4 text-center text-muted-foreground text-sm">
            Empty workspace
          </div>
        )}
      </div>
    </div>
  )
}
