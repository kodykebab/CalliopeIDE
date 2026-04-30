"use client"

import { useState, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { 
    ChevronRight, 
    ChevronDown, 
    Folder, 
    FolderOpen, 
    File, 
    FileText, 
    FileCode,
    RefreshCw,
    Loader2
} from "lucide-react"

// File icon mapping based on extension
const getFileIcon = (fileName) => {
    const ext = fileName.split('.').pop()?.toLowerCase()
    
    switch (ext) {
        case 'js':
        case 'jsx':
        case 'ts':
        case 'tsx':
            return <FileCode className="w-4 h-4 text-yellow-400 shrink-0" />
        case 'py':
            return <FileCode className="w-4 h-4 text-blue-400 shrink-0" />
        case 'rs':
            return <FileCode className="w-4 h-4 text-orange-400 shrink-0" />
        case 'css':
        case 'scss':
            return <FileCode className="w-4 h-4 text-purple-400 shrink-0" />
        case 'html':
        case 'htm':
            return <FileCode className="w-4 h-4 text-orange-500 shrink-0" />
        case 'json':
            return <FileText className="w-4 h-4 text-green-400 shrink-0" />
        case 'md':
            return <FileText className="w-4 h-4 text-gray-400 shrink-0" />
        case 'toml':
        case 'yaml':
        case 'yml':
            return <FileText className="w-4 h-4 text-cyan-400 shrink-0" />
        default:
            return <File className="w-4 h-4 text-gray-400 shrink-0" />
    }
}

const TreeNode = ({ 
    node, 
    level = 0, 
    onFileSelect, 
    activeFile, 
    expandedNodes, 
    onToggleExpand,
    projectPath 
}) => {
    const isExpanded = expandedNodes.has(node.path)
    const isActive = activeFile === (projectPath && node.path ? 
        `${projectPath}/${node.path}`.replace(/\\/g, '/') : 
        null)
    
    const handleClick = () => {
        if (node.type === 'directory') {
            onToggleExpand(node.path)
        } else if (node.type === 'file') {
            const fullPath = projectPath && node.path ? 
                `${projectPath}/${node.path}`.replace(/\\/g, '/') : 
                node.path
            onFileSelect(fullPath)
        }
    }

    return (
        <div>
            <div
                onClick={handleClick}
                className={[
                    "flex items-center gap-1 px-2 py-1.5 rounded hover:bg-gray-700 cursor-pointer transition-colors",
                    isActive ? "bg-gray-700 border-l-2 border-blue-400" : "",
                    level > 0 ? `ml-${Math.min(level * 4, 16)}` : ""
                ].join(" ")}
                style={{ marginLeft: level > 0 ? `${level * 16}px` : 0 }}
            >
                {node.type === 'directory' && (
                    <motion.div
                        animate={{ rotate: isExpanded ? 90 : 0 }}
                        transition={{ duration: 0.2 }}
                        className="shrink-0"
                    >
                        <ChevronRight className="w-3 h-3 text-gray-500" />
                    </motion.div>
                )}
                
                {node.type === 'directory' ? (
                    isExpanded ? (
                        <FolderOpen className="w-4 h-4 text-blue-400 shrink-0" />
                    ) : (
                        <Folder className="w-4 h-4 text-blue-400 shrink-0" />
                    )
                ) : (
                    getFileIcon(node.name)
                )}
                
                <span className="text-sm truncate">{node.name}</span>
            </div>
            
            <AnimatePresence>
                {node.type === 'directory' && isExpanded && node.children && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                        className="overflow-hidden"
                    >
                        {node.children.map((child) => (
                            <TreeNode
                                key={child.path}
                                node={child}
                                level={level + 1}
                                onFileSelect={onFileSelect}
                                activeFile={activeFile}
                                expandedNodes={expandedNodes}
                                onToggleExpand={onToggleExpand}
                                projectPath={projectPath}
                            />
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}

export default function FileExplorer({ projectId, onFileSelect, activeFile }) {
    const [fileTree, setFileTree] = useState(null)
    const [expandedNodes, setExpandedNodes] = useState(new Set(['']))
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [projectPath, setProjectPath] = useState(null)

    const fetchFileTree = useCallback(async () => {
        if (!projectId) return

        setLoading(true)
        setError(null)
        
        try {
            const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
            if (!token) {
                setError("Authentication required")
                return
            }

            const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000"
            const response = await fetch(`${BACKEND_URL}/api/projects/${projectId}/files/tree`, {
                headers: { Authorization: `Bearer ${token}` }
            })

            if (!response.ok) {
                throw new Error(`Failed to fetch file tree: ${response.status}`)
            }

            const data = await response.json()
            if (data.success) {
                setFileTree(data.tree)
                setProjectPath(data.project_path)
            } else {
                setError(data.error || "Failed to load file tree")
            }
        } catch (err) {
            console.error("File tree fetch error:", err)
            setError(err.message || "Network error")
        } finally {
            setLoading(false)
        }
    }, [projectId])

    useEffect(() => {
        fetchFileTree()
    }, [fetchFileTree])

    const toggleExpand = useCallback((path) => {
        setExpandedNodes(prev => {
            const next = new Set(prev)
            if (next.has(path)) {
                next.delete(path)
            } else {
                next.add(path)
            }
            return next
        })
    }, [])

    const handleRefresh = () => {
        fetchFileTree()
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center p-8">
                <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
                <span className="ml-2 text-sm text-gray-400">Loading files...</span>
            </div>
        )
    }

    if (error) {
        return (
            <div className="p-4">
                <div className="text-red-400 text-sm mb-3">{error}</div>
                <button
                    onClick={handleRefresh}
                    className="flex items-center gap-2 px-3 py-1.5 text-xs bg-gray-700 hover:bg-gray-600 rounded transition-colors"
                >
                    <RefreshCw className="w-3 h-3" />
                    Retry
                </button>
            </div>
        )
    }

    if (!fileTree) {
        return (
            <div className="flex items-center justify-center p-8">
                <span className="text-sm text-gray-400">No files found</span>
            </div>
        )
    }

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700">
                <span className="text-xs font-medium text-gray-300">Explorer</span>
                <button
                    onClick={handleRefresh}
                    className="p-1 rounded hover:bg-gray-700 transition-colors"
                    title="Refresh"
                >
                    <RefreshCw className="w-3 h-3 text-gray-400" />
                </button>
            </div>
            
            {/* File Tree */}
            <div className="flex-1 overflow-y-auto p-2">
                <TreeNode
                    node={fileTree}
                    onFileSelect={onFileSelect}
                    activeFile={activeFile}
                    expandedNodes={expandedNodes}
                    onToggleExpand={toggleExpand}
                    projectPath={projectPath}
                />
            </div>
        </div>
    )
}
