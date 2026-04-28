/**
 * FileExplorer — resolves issue #52
 *
 * A dynamic sidebar tree that:
 *   - Fetches the real workspace structure from GET /api/projects/:id/files/tree
 *   - Supports expand/collapse of folders
 *   - Opens files in the Monaco editor via onFileSelect callback
 *   - Reflects real workspace state (re-fetches when `refreshKey` changes)
 *   - Shows loading skeleton and error states
 */

import { useState, useEffect, useCallback, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
    ChevronRight,
    ChevronDown,
    FolderOpen,
    Folder,
    FileCode,
    FileText,
    RefreshCw,
    AlertCircle,
} from "lucide-react"

// ── File-type icon map ────────────────────────────────────────────────────────
const EXT_ICONS = {
    ".rs":    <FileCode  className="w-3.5 h-3.5 text-orange-400 shrink-0" />,
    ".ts":    <FileCode  className="w-3.5 h-3.5 text-blue-400   shrink-0" />,
    ".tsx":   <FileCode  className="w-3.5 h-3.5 text-blue-400   shrink-0" />,
    ".js":    <FileCode  className="w-3.5 h-3.5 text-yellow-400 shrink-0" />,
    ".jsx":   <FileCode  className="w-3.5 h-3.5 text-yellow-400 shrink-0" />,
    ".py":    <FileCode  className="w-3.5 h-3.5 text-green-400  shrink-0" />,
    ".toml":  <FileText  className="w-3.5 h-3.5 text-gray-400   shrink-0" />,
    ".json":  <FileText  className="w-3.5 h-3.5 text-yellow-300 shrink-0" />,
    ".md":    <FileText  className="w-3.5 h-3.5 text-gray-300   shrink-0" />,
    ".yml":   <FileText  className="w-3.5 h-3.5 text-red-400    shrink-0" />,
    ".yaml":  <FileText  className="w-3.5 h-3.5 text-red-400    shrink-0" />,
    ".css":   <FileCode  className="w-3.5 h-3.5 text-pink-400   shrink-0" />,
    ".html":  <FileCode  className="w-3.5 h-3.5 text-orange-300 shrink-0" />,
}

function fileIcon(extension) {
    return EXT_ICONS[extension] || (
        <FileText className="w-3.5 h-3.5 text-gray-500 shrink-0" />
    )
}

// ── Single tree node ──────────────────────────────────────────────────────────
function TreeNode({ node, depth, activeFile, onFileSelect }) {
    const [open, setOpen] = useState(depth < 1)   // top-level folders open by default

    const isDir  = node.type === "directory"
    const isFile = node.type === "file"
    const isActive = isFile && activeFile === node.path

    const indent = depth * 12  // px per level

    const handleClick = () => {
        if (isDir)  setOpen((v) => !v)
        if (isFile) onFileSelect(node.path)
    }

    return (
        <div>
            {/* Row */}
            <div
                role={isFile ? "button" : "treeitem"}
                aria-expanded={isDir ? open : undefined}
                aria-selected={isActive}
                tabIndex={0}
                onClick={handleClick}
                onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && handleClick()}
                style={{ paddingLeft: `${indent + 8}px` }}
                className={[
                    "flex items-center gap-1.5 py-[3px] pr-2 rounded cursor-pointer select-none",
                    "text-sm transition-colors duration-100",
                    isActive
                        ? "bg-blue-900/60 text-white border-l-2 border-blue-400"
                        : "text-gray-300 hover:bg-gray-700/60 hover:text-white",
                ].join(" ")}
            >
                {/* Folder chevron / file placeholder */}
                <span className="w-3.5 shrink-0 flex items-center justify-center">
                    {isDir
                        ? (open
                            ? <ChevronDown  className="w-3 h-3 text-gray-400" />
                            : <ChevronRight className="w-3 h-3 text-gray-400" />)
                        : null
                    }
                </span>

                {/* Icon */}
                {isDir
                    ? (open
                        ? <FolderOpen className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                        : <Folder     className="w-3.5 h-3.5 text-blue-400 shrink-0" />)
                    : fileIcon(node.extension || "")
                }

                {/* Name */}
                <span className="truncate">{node.name}</span>
            </div>

            {/* Children */}
            {isDir && (
                <AnimatePresence initial={false}>
                    {open && node.children && node.children.length > 0 && (
                        <motion.div
                            key="children"
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.15, ease: "easeInOut" }}
                            style={{ overflow: "hidden" }}
                        >
                            {node.children.map((child) => (
                                <TreeNode
                                    key={child.path}
                                    node={child}
                                    depth={depth + 1}
                                    activeFile={activeFile}
                                    onFileSelect={onFileSelect}
                                />
                            ))}
                        </motion.div>
                    )}
                    {open && isDir && node.children && node.children.length === 0 && (
                        <p
                            style={{ paddingLeft: `${(depth + 1) * 12 + 8 + 14}px` }}
                            className="py-1 text-xs text-gray-600 italic"
                        >
                            empty
                        </p>
                    )}
                </AnimatePresence>
            )}
        </div>
    )
}

// ── Loading skeleton ──────────────────────────────────────────────────────────
function TreeSkeleton() {
    const rows = [
        { w: "60%", indent: 8 },
        { w: "45%", indent: 22 },
        { w: "50%", indent: 22 },
        { w: "55%", indent: 8 },
        { w: "40%", indent: 22 },
        { w: "65%", indent: 8 },
    ]
    return (
        <div className="p-2 space-y-1 animate-pulse">
            {rows.map(({ w, indent }, i) => (
                <div
                    key={i}
                    style={{ paddingLeft: indent, width: w }}
                    className="h-4 bg-gray-700/60 rounded"
                />
            ))}
        </div>
    )
}

// ── Main component ────────────────────────────────────────────────────────────
/**
 * @param {{ projectId: number|null, token: string|null, backendUrl: string,
 *           activeFile: string|null, onFileSelect: (path:string)=>void,
 *           refreshKey: number }} props
 */
export default function FileExplorer({
    projectId,
    token,
    backendUrl,
    activeFile,
    onFileSelect,
    refreshKey = 0,
}) {
    const [tree,    setTree]    = useState([])
    const [loading, setLoading] = useState(false)
    const [error,   setError]   = useState(null)
    const abortRef = useRef(null)

    const fetchTree = useCallback(async () => {
        if (!projectId || !token) {
            setTree([])
            return
        }

        // Cancel any in-flight request
        abortRef.current?.abort()
        abortRef.current = new AbortController()

        setLoading(true)
        setError(null)

        try {
            const res = await fetch(
                `${backendUrl}/api/projects/${projectId}/files/tree`,
                {
                    headers: { Authorization: `Bearer ${token}` },
                    signal: abortRef.current.signal,
                }
            )

            if (!res.ok) {
                const data = await res.json().catch(() => ({}))
                throw new Error(data.error || `HTTP ${res.status}`)
            }

            const data = await res.json()
            if (data.success) {
                setTree(data.tree || [])
            } else {
                throw new Error(data.error || "Unknown error")
            }
        } catch (err) {
            if (err.name === "AbortError") return  // component unmounted / re-fetching
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }, [projectId, token, backendUrl])

    // Re-fetch whenever projectId, token, or refreshKey changes
    useEffect(() => {
        fetchTree()
        return () => abortRef.current?.abort()
    }, [fetchTree, refreshKey])

    // ── Render ────────────────────────────────────────────────────────────────
    return (
        <div className="flex flex-col h-full min-h-0">
            {/* Header row */}
            <div className="flex items-center justify-between px-3 py-1.5 border-b border-gray-700/50">
                <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-500">
                    Explorer
                </span>
                <button
                    onClick={fetchTree}
                    title="Refresh file tree"
                    aria-label="Refresh file tree"
                    className="p-0.5 rounded text-gray-500 hover:text-gray-300 transition-colors"
                >
                    <RefreshCw
                        className={`w-3 h-3 ${loading ? "animate-spin" : ""}`}
                    />
                </button>
            </div>

            {/* Body */}
            <div
                role="tree"
                aria-label="Project file tree"
                className="flex-1 overflow-y-auto py-1 text-sm"
            >
                {loading && tree.length === 0 && <TreeSkeleton />}

                {!loading && error && (
                    <div className="flex flex-col items-center gap-2 p-4 text-center">
                        <AlertCircle className="w-5 h-5 text-red-400" />
                        <p className="text-xs text-gray-400">{error}</p>
                        <button
                            onClick={fetchTree}
                            className="text-xs text-blue-400 hover:underline"
                        >
                            Retry
                        </button>
                    </div>
                )}

                {!loading && !error && tree.length === 0 && projectId && (
                    <p className="px-4 py-3 text-xs text-gray-500 italic">
                        No files found in workspace.
                    </p>
                )}

                {!projectId && (
                    <p className="px-4 py-3 text-xs text-gray-500 italic">
                        No project loaded.
                    </p>
                )}

                {tree.map((node) => (
                    <TreeNode
                        key={node.path}
                        node={node}
                        depth={0}
                        activeFile={activeFile}
                        onFileSelect={onFileSelect}
                    />
                ))}
            </div>
        </div>
    )
}
