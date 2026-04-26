import React, { useState, useEffect, useCallback } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { 
    Folder, 
    FolderOpen, 
    File, 
    ChevronRight, 
    ChevronDown, 
    RefreshCw,
    FileText,
    Settings,
    Code,
    Terminal
} from "lucide-react"
import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000"

function cn(...inputs) {
    return twMerge(clsx(inputs))
}

const FileIcon = ({ fileName, isDir }) => {
    if (isDir) return null; // Handled by folder component
    
    const ext = fileName.split('.').pop().toLowerCase();
    
    switch (ext) {
        case 'rs':
            return <Code className="w-4 h-4 text-orange-400" />;
        case 'py':
            return <Code className="w-4 h-4 text-blue-400" />;
        case 'js':
        case 'jsx':
            return <Code className="w-4 h-4 text-yellow-400" />;
        case 'ts':
        case 'tsx':
            return <Code className="w-4 h-4 text-blue-500" />;
        case 'json':
            return <FileText className="w-4 h-4 text-yellow-300" />;
        case 'toml':
            return <Settings className="w-4 h-4 text-gray-400" />;
        case 'md':
            return <FileText className="w-4 h-4 text-blue-300" />;
        case 'sh':
            return <Terminal className="w-4 h-4 text-green-400" />;
        default:
            return <File className="w-4 h-4 text-gray-400" />;
    }
};

const TreeItem = ({ item, level = 0, onFileSelect, activeFile }) => {
    const [isOpen, setIsOpen] = useState(false);
    const isSelected = activeFile === item.path;

    const toggleOpen = (e) => {
        e.stopPropagation();
        if (item.is_dir) {
            setIsOpen(!isOpen);
        }
    };

    const handleClick = () => {
        if (item.is_dir) {
            setIsOpen(!isOpen);
        } else {
            onFileSelect(item.path);
        }
    };

    return (
        <div className="select-none">
            <div
                onClick={handleClick}
                className={cn(
                    "flex items-center gap-1 px-2 py-1 rounded cursor-pointer transition-colors group",
                    isSelected ? "bg-gray-700 text-white" : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
                )}
                style={{ paddingLeft: `${level * 12 + 8}px` }}
            >
                {item.is_dir ? (
                    <div className="flex items-center gap-1 w-full overflow-hidden">
                        <span className="shrink-0">
                            {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        </span>
                        <span className="shrink-0 text-blue-400">
                            {isOpen ? <FolderOpen className="w-4 h-4" /> : <Folder className="w-4 h-4" />}
                        </span>
                        <span className="text-sm truncate font-medium">{item.name}</span>
                    </div>
                ) : (
                    <div className="flex items-center gap-2 w-full overflow-hidden">
                        <span className="w-4 shrink-0" /> {/* Spacer for chevron */}
                        <span className="shrink-0">
                            <FileIcon fileName={item.name} isDir={false} />
                        </span>
                        <span className={cn(
                            "text-sm truncate",
                            isSelected ? "font-semibold" : ""
                        )}>{item.name}</span>
                    </div>
                )}
            </div>

            <AnimatePresence>
                {item.is_dir && isOpen && item.children && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2, ease: "easeInOut" }}
                        className="overflow-hidden"
                    >
                        {item.children.map((child) => (
                            <TreeItem
                                key={child.path}
                                item={child}
                                level={level + 1}
                                onFileSelect={onFileSelect}
                                activeFile={activeFile}
                            />
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export default function FileExplorer({ projectId, onFileSelect, activeFile }) {
    const [tree, setTree] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const fetchTree = useCallback(async () => {
        if (!projectId) return;
        
        setLoading(true);
        setError(null);
        
        const token = localStorage.getItem("access_token");
        try {
            const res = await fetch(`${BACKEND_URL}/api/projects/${projectId}/files/tree`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            const data = await res.json();
            
            if (data.success) {
                setTree(data.tree);
            } else {
                setError(data.error || "Failed to load tree");
            }
        } catch (err) {
            setError("Network error loading tree");
        } finally {
            setLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        fetchTree();
    }, [fetchTree]);

    if (!projectId) {
        return (
            <div className="p-4 text-center text-gray-500 text-sm italic">
                No project workspace loaded.
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full">
            <div className="flex items-center justify-between px-4 py-2 bg-[#161B22] border-b border-gray-700/50 sticky top-0 z-10">
                <span className="text-[10px] uppercase tracking-wider font-bold text-gray-500">Workspace</span>
                <button 
                    onClick={fetchTree}
                    disabled={loading}
                    className="p-1 hover:bg-gray-700 rounded transition-colors disabled:opacity-50"
                    title="Refresh Explorer"
                >
                    <RefreshCw className={cn("w-3 h-3 text-gray-400", loading && "animate-spin")} />
                </button>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar p-1">
                {loading && !tree ? (
                    <div className="flex flex-col items-center justify-center h-20 gap-2">
                        <div className="w-4 h-4 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
                        <span className="text-xs text-gray-500">Loading structure...</span>
                    </div>
                ) : error ? (
                    <div className="p-4 text-center">
                        <p className="text-xs text-red-400 mb-2">{error}</p>
                        <button 
                            onClick={fetchTree}
                            className="text-[10px] px-2 py-1 bg-gray-800 hover:bg-gray-700 rounded text-gray-300 transition-colors"
                        >
                            Retry
                        </button>
                    </div>
                ) : tree ? (
                    <div className="py-1">
                        {tree.children && tree.children.length > 0 ? (
                            tree.children.map((item) => (
                                <TreeItem
                                    key={item.path}
                                    item={item}
                                    onFileSelect={onFileSelect}
                                    activeFile={activeFile}
                                />
                            ))
                        ) : (
                            <div className="p-4 text-center text-xs text-gray-500 italic">
                                Project directory is empty.
                            </div>
                        )}
                    </div>
                ) : null}
            </div>
        </div>
    );
}
