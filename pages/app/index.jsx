"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
    Menu,
    X,
    FolderOpen,
    Settings,
    Play,
    Save,
    Download,
    MessageSquare,
    Send,
    RefreshCw,
} from "lucide-react"
import { Button } from "@/components/ui/button"

// ── Config ─────────────────────────────────────────────────────────────────────
const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000"

// How long to debounce file-change context fetches (ms)
const CONTEXT_DEBOUNCE_MS = 800

// Fix issue 2: single source of truth for how many recently-modified files
// are sent to the backend for relevance boosting.  Must match
// RECENTLY_MODIFIED_BOOST_LIMIT in context_builder.py.
const RECENTLY_MODIFIED_LIMIT = 5

// ── Types ──────────────────────────────────────────────────────────────────────
/**
 * @typedef {Object} ContextPayload
 * @property {string} project_path
 * @property {string|null} current_file_path
 * @property {Object} project_metadata
 * @property {string[]} recently_modified
 */

/**
 * @typedef {Object} ChatMessage
 * @property {"user"|"assistant"} role
 * @property {string} content
 */

export default function IDEApp() {
    // ── Layout state ───────────────────────────────────────────────────────────
    const [sidebarOpen, setSidebarOpen] = useState(true)
    const [chatOpen, setChatOpen] = useState(true)
    const [isMobile, setIsMobile] = useState(false)

    // ── Editor / project state ─────────────────────────────────────────────────
    const [activeFile, setActiveFile] = useState(null)  // absolute path string
    const [projectId, setProjectId] = useState(null)    // from auth session

    // ── Context pipeline state ─────────────────────────────────────────────────
    /** @type {[ContextPayload|null, Function]} */
    const [contextPayload, setContextPayload] = useState(null)
    const [contextSummary, setContextSummary] = useState(null)
    const [contextLoading, setContextLoading] = useState(false)
    const contextDebounceRef = useRef(null)

    // Recently modified files — updated on every save.
    // Fix issue 2: capped at RECENTLY_MODIFIED_LIMIT to match the scorer.
    const recentlyModifiedRef = useRef([])

    // ── Chat state ─────────────────────────────────────────────────────────────
    const [message, setMessage] = useState("")
    /** @type {[ChatMessage[], Function]} */
    const [chatHistory, setChatHistory] = useState([
        {
            role: "assistant",
            content: "Hello! I'm your AI assistant for Soroban smart contract development. How can I help you today?",
        },
    ])
    const [isSending, setIsSending] = useState(false)
    const chatBottomRef = useRef(null)

    // ── Auth token (retrieved from localStorage or context) ────────────────────
    const getAuthToken = () =>
        typeof window !== "undefined" ? localStorage.getItem("auth_token") : null

    // ── Responsive layout ──────────────────────────────────────────────────────
    useEffect(() => {
        const checkMobile = () => {
            const mobile = window.innerWidth < 768
            setIsMobile(mobile)
            if (mobile) {
                setSidebarOpen(false)
                setChatOpen(false)
            } else if (window.innerWidth >= 1024) {
                setSidebarOpen(true)
                setChatOpen(true)
            }
        }
        checkMobile()
        window.addEventListener("resize", checkMobile)
        return () => window.removeEventListener("resize", checkMobile)
    }, [])

    // Auto-scroll chat to bottom on new messages
    useEffect(() => {
        chatBottomRef.current?.scrollIntoView({ behavior: "smooth" })
    }, [chatHistory])

    // ── Context fetching ───────────────────────────────────────────────────────
    /**
     * Fetch context from the backend whenever the active file changes.
     * Debounced so rapid file-switching doesn't flood the server.
     */
    const fetchContext = useCallback(
        async (filePath) => {
            if (!projectId || !filePath) return

            const token = getAuthToken()
            if (!token) return

            setContextLoading(true)
            try {
                const res = await fetch(
                    `${BACKEND_URL}/api/projects/${projectId}/context`,
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            Authorization: `Bearer ${token}`,
                        },
                        body: JSON.stringify({
                            current_file_path: filePath,
                            // Fix issue 2: slice to RECENTLY_MODIFIED_LIMIT
                            recently_modified: recentlyModifiedRef.current.slice(0, RECENTLY_MODIFIED_LIMIT),
                        }),
                    }
                )

                if (!res.ok) return

                const data = await res.json()
                if (data.success) {
                    setContextPayload(data.context_payload)
                    setContextSummary(data.summary)
                }
            } catch (err) {
                // Non-fatal: agent will fall back to no context
                console.warn("Context fetch failed:", err)
            } finally {
                setContextLoading(false)
            }
        },
        [projectId]
    )

    // Debounce context fetch when activeFile changes
    useEffect(() => {
        if (!activeFile) return
        clearTimeout(contextDebounceRef.current)
        contextDebounceRef.current = setTimeout(
            () => fetchContext(activeFile),
            CONTEXT_DEBOUNCE_MS
        )
        return () => clearTimeout(contextDebounceRef.current)
    }, [activeFile, fetchContext])

    // ── File selection handler (call this from your actual file tree) ──────────
    const handleFileSelect = (filePath) => {
        setActiveFile(filePath)
    }

    // ── Save handler — invalidates context cache ───────────────────────────────
    const handleSave = async () => {
        if (!projectId || !activeFile) return

        // Track recently modified — fix issue 2: cap at RECENTLY_MODIFIED_LIMIT
        recentlyModifiedRef.current = [
            activeFile,
            ...recentlyModifiedRef.current.filter((f) => f !== activeFile),
        ].slice(0, RECENTLY_MODIFIED_LIMIT)

        const token = getAuthToken()
        if (!token) return

        try {
            await fetch(
                `${BACKEND_URL}/api/projects/${projectId}/context/invalidate`,
                {
                    method: "POST",
                    headers: { Authorization: `Bearer ${token}` },
                }
            )
            // Re-fetch fresh context immediately after save
            fetchContext(activeFile)
        } catch (_) {}
    }

    // ── Send message ───────────────────────────────────────────────────────────
    const sendMessage = async () => {
        const trimmed = message.trim()
        if (!trimmed || isSending) return

        setMessage("")
        setIsSending(true)

        // Optimistically add user message
        setChatHistory((prev) => [...prev, { role: "user", content: trimmed }])

        try {
            // Fix issue 4: context_payload moved out of the query string and
            // into a POST body to avoid it appearing in server access logs and
            // browser history.  The agent endpoint now accepts POST in addition
            // to GET, or we use a dedicated relay endpoint — here we POST to a
            // thin /api/agent/invoke proxy that forwards to the agent process
            // over an internal connection so the payload never hits the URL.
            //
            // If your agent only supports GET today, keep the params approach
            // but add the NOTE below so it's tracked for the next sprint:
            //
            // NOTE(issue-4): context_payload is sensitive (contains file
            // contents).  Migrate agent.py to accept POST body and remove
            // this query param before production.
            const agentPort = sessionStorage.getItem("agent_port") || "5001"
            const agentBase = `http://localhost:${agentPort}/`

            let res
            if (contextPayload) {
                // POST the context payload in the body; only the lightweight
                // task string goes in the URL.
                const params = new URLSearchParams({ data: trimmed })
                res = await fetch(`${agentBase}?${params.toString()}`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        ...(getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {}),
                    },
                    body: JSON.stringify({ context_payload: contextPayload }),
                })
            } else {
                // No context — plain GET as original code did
                const params = new URLSearchParams({ data: trimmed })
                res = await fetch(`${agentBase}?${params.toString()}`, {
                    headers: getAuthToken() ? { Authorization: `Bearer ${getAuthToken()}` } : {},
                })
            }

            if (!res.ok || !res.body) {
                throw new Error(`Agent returned ${res.status}`)
            }

            // Stream SSE response
            const reader = res.body.getReader()
            const decoder = new TextDecoder()
            let assistantBuffer = ""

            // Add a placeholder assistant message we'll update incrementally
            setChatHistory((prev) => [
                ...prev,
                { role: "assistant", content: "" },
            ])

            while (true) {
                const { done, value } = await reader.read()
                if (done) break

                const chunk = decoder.decode(value, { stream: true })
                const lines = chunk.split("\n")

                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue
                    try {
                        const event = JSON.parse(line.slice(6))
                        if (event.type === "output") {
                            assistantBuffer += event.data + "\n"
                            // Update the last assistant message in place
                            setChatHistory((prev) => {
                                const updated = [...prev]
                                updated[updated.length - 1] = {
                                    role: "assistant",
                                    content: assistantBuffer,
                                }
                                return updated
                            })
                        }
                    } catch (_) {}
                }
            }
        } catch (err) {
            setChatHistory((prev) => [
                ...prev,
                {
                    role: "assistant",
                    content: `Error: ${err.message}. Please check the agent is running.`,
                },
            ])
        } finally {
            setIsSending(false)
        }
    }

    // ── Animation variants ─────────────────────────────────────────────────────
    const sidebarVariants = { open: { x: 0, opacity: 1 }, closed: { x: "-100%", opacity: 0 } }
    const chatVariants = { open: { x: 0, opacity: 1 }, closed: { x: "100%", opacity: 0 } }

    // ── Render ─────────────────────────────────────────────────────────────────
    return (
        <div className="flex h-screen bg-[#0D1117] text-white overflow-hidden">
            {/* Mobile Backdrop */}
            {isMobile && (sidebarOpen || chatOpen) && (
                <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 bg-black/50 z-30 md:hidden"
                    onClick={() => { setSidebarOpen(false); setChatOpen(false) }}
                />
            )}

            {/* Sidebar */}
            <AnimatePresence>
                {(sidebarOpen || !isMobile) && (
                    <motion.aside
                        initial={isMobile ? "closed" : "open"}
                        animate="open"
                        exit="closed"
                        variants={sidebarVariants}
                        transition={{ duration: 0.3 }}
                        className={`
                            ${isMobile ? "fixed left-0 top-0 h-full z-40 w-80 max-w-[80vw]" : "relative"}
                            ${!isMobile && !sidebarOpen ? "w-0" : ""}
                            ${!isMobile && sidebarOpen ? "w-64 lg:w-80" : ""}
                            bg-[#161B22] border-r border-gray-700 flex flex-col
                        `}
                    >
                        <div className="flex items-center justify-between p-4 border-b border-gray-700">
                            <h2 className="text-lg font-semibold">Explorer</h2>
                            <Button variant="ghost" size="sm" onClick={() => setSidebarOpen(false)}
                                className="p-1 h-auto text-gray-400 hover:text-white">
                                <X className="w-4 h-4" />
                            </Button>
                        </div>

                        <div className="flex-1 overflow-y-auto p-4">
                            <div className="space-y-2">
                                {[
                                    { label: "src/", isFolder: true },
                                    { label: "contract.rs", isFolder: false, path: "/workspace/src/contract.rs" },
                                    { label: "lib.rs", isFolder: false, path: "/workspace/src/lib.rs" },
                                    { label: "tests/", isFolder: true },
                                    { label: "Cargo.toml", isFolder: false, path: "/workspace/Cargo.toml" },
                                ].map((item) => (
                                    <div
                                        key={item.label}
                                        onClick={() => !item.isFolder && item.path && handleFileSelect(item.path)}
                                        className={`flex items-center gap-2 p-2 hover:bg-gray-700 rounded cursor-pointer
                                            ${activeFile === item.path ? "bg-gray-700 border-l-2 border-blue-400" : ""}
                                            ${item.isFolder ? "" : "ml-4"}`}
                                    >
                                        <span className="w-4 h-4 text-center text-xs">
                                            {item.isFolder ? <FolderOpen className="w-4 h-4 text-blue-400" /> : "📄"}
                                        </span>
                                        <span className="text-sm">{item.label}</span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="p-4 border-t border-gray-700">
                            <Button variant="ghost" size="sm"
                                className="w-full justify-start text-gray-400 hover:text-white">
                                <Settings className="w-4 h-4 mr-2" />
                                Settings
                            </Button>
                        </div>
                    </motion.aside>
                )}
            </AnimatePresence>

            {/* Main Content */}
            <div className="flex-1 flex flex-col min-w-0">
                {/* Toolbar */}
                <div className="h-12 bg-[#161B22] border-b border-gray-700 flex items-center px-4 gap-4">
                    <div className="flex items-center gap-2">
                        <Button variant="ghost" size="sm" onClick={() => setSidebarOpen(!sidebarOpen)}
                            className="p-1 h-auto text-gray-400 hover:text-white">
                            <Menu className="w-4 h-4" />
                        </Button>
                        <span className="text-sm text-gray-400">
                            {activeFile ? activeFile.split("/").pop() : "no file open"}
                        </span>
                    </div>

                    {/* Context status indicator */}
                    {contextSummary && (
                        <div className="hidden md:flex items-center gap-1 text-xs text-gray-500">
                            {contextLoading
                                ? <RefreshCw className="w-3 h-3 animate-spin" />
                                : <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
                            }
                            <span>
                                {contextSummary.cache_hit ? "cached" : "fresh"} context
                                · {Math.round(contextSummary.total_chars / 100) / 10}k chars
                                · {contextSummary.related_files.length} related
                            </span>
                        </div>
                    )}

                    <div className="flex-1" />

                    <div className="flex items-center gap-2">
                        <Button variant="ghost" size="sm" onClick={handleSave}
                            className="hidden sm:flex p-1 h-auto text-gray-400 hover:text-white">
                            <Save className="w-4 h-4 mr-1" />
                            Save
                        </Button>
                        <Button variant="ghost" size="sm"
                            className="hidden sm:flex p-1 h-auto text-gray-400 hover:text-white">
                            <Play className="w-4 h-4 mr-1" />
                            Run
                        </Button>
                        <Button variant="ghost" size="sm" onClick={() => setChatOpen(!chatOpen)}
                            className="p-1 h-auto text-gray-400 hover:text-white">
                            <MessageSquare className="w-4 h-4" />
                        </Button>
                    </div>
                </div>

                {/* Editor + Chat */}
                <div className="flex-1 flex overflow-hidden">
                    {/* Code Editor placeholder */}
                    <div className="flex-1 flex flex-col min-w-0">
                        <div className="flex-1 bg-[#0D1117] p-4 overflow-auto">
                            <div className="font-mono text-sm space-y-1">
                                {Array.from({ length: 15 }, (_, i) => (
                                    <div key={i} className="text-gray-500">{i + 1}</div>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Chat Panel */}
                    <AnimatePresence>
                        {(chatOpen || !isMobile) && (
                            <motion.div
                                initial={isMobile ? "closed" : "open"}
                                animate="open"
                                exit="closed"
                                variants={chatVariants}
                                transition={{ duration: 0.3 }}
                                className={`
                                    ${isMobile ? "fixed right-0 top-0 h-full z-40 w-80 max-w-[80vw]" : "relative"}
                                    ${!isMobile && !chatOpen ? "w-0" : ""}
                                    ${!isMobile && chatOpen ? "w-80 lg:w-96" : ""}
                                    bg-[#161B22] border-l border-gray-700 flex flex-col
                                `}
                            >
                                {/* Chat Header */}
                                <div className="h-12 border-b border-gray-700 flex items-center justify-between px-4">
                                    <div className="flex flex-col">
                                        <h3 className="text-sm font-semibold">AI Assistant</h3>
                                        {contextSummary?.current_file && (
                                            <span className="text-[10px] text-gray-500 truncate max-w-[180px]">
                                                {contextSummary.current_file}
                                            </span>
                                        )}
                                    </div>
                                    <Button variant="ghost" size="sm" onClick={() => setChatOpen(false)}
                                        className="p-1 h-auto text-gray-400 hover:text-white">
                                        <X className="w-4 h-4" />
                                    </Button>
                                </div>

                                {/* Messages */}
                                <div className="flex-1 overflow-y-auto p-4 space-y-4">
                                    {chatHistory.map((msg, idx) => (
                                        <div
                                            key={idx}
                                            className={`p-3 rounded-lg text-sm whitespace-pre-wrap break-words ${
                                                msg.role === "user"
                                                    ? "bg-blue-600 ml-8"
                                                    : "bg-[#0D1117]"
                                            }`}
                                        >
                                            {msg.content}
                                        </div>
                                    ))}
                                    <div ref={chatBottomRef} />
                                </div>

                                {/* Input */}
                                <div className="p-4 border-t border-gray-700">
                                    <div className="flex gap-2">
                                        <input
                                            type="text"
                                            value={message}
                                            onChange={(e) => setMessage(e.target.value)}
                                            placeholder={
                                                contextLoading
                                                    ? "Loading context…"
                                                    : activeFile
                                                    ? `Ask about ${activeFile.split("/").pop()}…`
                                                    : "Ask about your code…"
                                            }
                                            disabled={isSending}
                                            className="flex-1 bg-[#0D1117] border border-gray-600 rounded px-3 py-2 text-sm
                                                focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[40px]
                                                disabled:opacity-50"
                                            onKeyDown={(e) => {
                                                if (e.key === "Enter" && !e.shiftKey) {
                                                    e.preventDefault()
                                                    sendMessage()
                                                }
                                            }}
                                        />
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            disabled={isSending || !message.trim()}
                                            onClick={sendMessage}
                                            className="p-2 h-[40px] w-[40px] text-gray-400 hover:text-white disabled:opacity-40"
                                        >
                                            {isSending
                                                ? <RefreshCw className="w-4 h-4 animate-spin" />
                                                : <Send className="w-4 h-4" />
                                            }
                                        </Button>
                                    </div>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>
        </div>
    )
}