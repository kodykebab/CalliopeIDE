"use client"

import { useState, useEffect, useCallback, useRef } from "react"
import { useRouter } from "next/router"
import { motion, AnimatePresence } from "framer-motion"
import ReactMarkdown from "react-markdown"

import {
    Menu,
    X,
    FolderOpen,
    Settings,
    Play,
    Save,
    MessageSquare,
    Send,
    LogOut,
    User,
    ChevronLeft,
    Zap,
    Rocket,
    Github,
    GitPullRequest,
    RefreshCw,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { getPublicKey, signTransaction, isConnected } from "@stellar/freighter-api"
import ContractInteraction from "@/components/ContractInteraction"
import FileExplorer from "@/components/FileExplorer"

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

// ── Token helpers ──────────────────────────────────────────────────────────────
function getToken()   { return typeof window !== "undefined" ? localStorage.getItem("access_token")  : null }
function getRefresh() { return typeof window !== "undefined" ? localStorage.getItem("refresh_token") : null }
function clearTokens() {
    localStorage.removeItem("access_token")
    localStorage.removeItem("refresh_token")
}

async function refreshAccessToken() {
    const refresh = getRefresh()
    if (!refresh) return null
    try {
        const res = await fetch(`${BACKEND_URL}/api/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refresh }),
        })
        if (!res.ok) return null
        const data = await res.json()
        if (data.access_token) {
            localStorage.setItem("access_token", data.access_token)
            return data.access_token
        }
    } catch { /* network error */ }
    return null
}

async function fetchCurrentUser(token) {
    try {
        let res = await fetch(`${BACKEND_URL}/api/auth/me`, {
            headers: { Authorization: `Bearer ${token}` },
        })
        if (res.status === 401) {
            const newToken = await refreshAccessToken()
            if (!newToken) return null
            res = await fetch(`${BACKEND_URL}/api/auth/me`, {
                headers: { Authorization: `Bearer ${newToken}` },
            })
        }
        if (!res.ok) return null
        const data = await res.json()
        return data.user ?? null
    } catch {
        return null
    }
}

// ── Static code preview ────────────────────────────────────────────────────────
const CODE_LINES = [
    { num: 1,  code: "" },
    { num: 2,  code: "use soroban_sdk::{contract, contractimpl, Env, Symbol};" },
    { num: 3,  code: "" },
    { num: 4,  code: "#[contract]" },
    { num: 5,  code: "pub struct TokenContract;" },
    { num: 6,  code: "" },
    { num: 7,  code: "#[contractimpl]" },
    { num: 8,  code: "impl TokenContract {" },
    { num: 9,  code: "    pub fn initialize(env: Env, admin: Address) {" },
    { num: 10, code: "        env.storage().instance().set(&Symbol::short(\"admin\"), &admin);" },
    { num: 11, code: "    }" },
    { num: 12, code: "" },
    { num: 13, code: "    pub fn mint(env: Env, to: Address, amount: i128) {" },
    { num: 14, code: "        // mint logic here" },
    { num: 15, code: "    }" },
    { num: 16, code: "}" },
]

export default function IDEApp() {
    const router = useRouter()

    // ── Auth state ─────────────────────────────────────────────────────────────
    const [user, setUser]               = useState(null)
    const [authLoading, setAuthLoading] = useState(true)

    // ── Layout state ───────────────────────────────────────────────────────────
    const [sidebarOpen, setSidebarOpen]   = useState(true)
    const [chatOpen, setChatOpen]         = useState(true)
    const [isMobile, setIsMobile]         = useState(false)
    const [userMenuOpen, setUserMenuOpen] = useState(false)
    const [sidebarTab, setSidebarTab]     = useState("explorer")

    // ── Editor / project state ─────────────────────────────────────────────────
    const [activeFile, setActiveFile] = useState(null)  // absolute path string
    const [projectId, setProjectId]   = useState(null)  // from auth session
    const [fileContent, setFileContent] = useState(CODE_LINES.map(l => l.code).join("\n"))
    const [saveStatus, setSaveStatus] = useState("idle") // "idle" | "saving" | "saved" | "error"

    // ── Deploy state ───────────────────────────────────────────────────────────
    const [isDeploying, setIsDeploying] = useState(false)
    const [contractId, setContractId]   = useState(null)

    // ── GitHub modal state ─────────────────────────────────────────────────────
    const [githubModalOpen, setGithubModalOpen] = useState(false)
    const [githubForm, setGithubForm] = useState({
        token: "",
        owner: "",
        repo: "",
        branch: "feature/calliope-changes",
        baseBranch: "main",
        filePath: "contract.rs",
        commitMessage: "Update contract from CalliopeIDE",
        createPR: false,
        prTitle: "Update smart contract",
        prBody: "",
    })
    const [githubStatus, setGithubStatus] = useState({ state: "idle", message: "", links: null })

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
    const [message, setMessage]       = useState("")
    /** @type {[ChatMessage[], Function]} */
    const [chatHistory, setChatHistory] = useState([
        {
            role: "assistant",
            content: "Hello! I'm your AI assistant for Soroban smart contract development. How can I help you today?",
        },
    ])
    const [isSending, setIsSending] = useState(false)
    const chatBottomRef   = useRef(null)
    const chatMessagesRef = useRef(null)

    // ── Auth token helper (unified) ────────────────────────────────────────────
    // Uses access_token key (from main branch token helpers above) so that
    // both the auth system and the context/agent calls share one token.
    const getAuthToken = () => getToken()

    // ── Auth init ──────────────────────────────────────────────────────────────
    useEffect(() => {
        async function init() {
            const token = getToken()
            if (!token) {
                router.replace("/login")
                return
            }
            const userData = await fetchCurrentUser(token)
            if (!userData) {
                clearTokens()
                router.replace("/login")
                return
            }
            setUser(userData)
            
            // Auto-setup or retrieve default project workspace
            try {
                const projRes = await fetch(`${BACKEND_URL}/api/projects/list`, {
                    headers: { Authorization: `Bearer ${token}` }
                })
                const projData = await projRes.json()
                if (projData.success && projData.projects.length > 0) {
                    setProjectId(projData.projects[0].id)
                } else {
                    const createRes = await fetch(`${BACKEND_URL}/api/projects/`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                        body: JSON.stringify({
                            project_name: "Default Workspace",
                            project_path: "./workspace"
                        })
                    })
                    const createData = await createRes.json()
                    if (createData.success) {
                        setProjectId(createData.project.id)
                    }
                }
            } catch (err) {
                console.warn("Failed to auto-setup project", err)
            }
            
            setAuthLoading(false)
        }
        init()
    }, [router])

    // ── Logout ─────────────────────────────────────────────────────────────────
    async function logout() {
        const token = getToken()
        if (token) {
            try {
                await fetch(`${BACKEND_URL}/api/auth/logout`, {
                    method: "POST",
                    headers: { Authorization: `Bearer ${token}` },
                })
            } catch { /* best-effort */ }
        }
        clearTokens()
        router.push("/login")
    }

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

    // ── Auto-scroll chat ───────────────────────────────────────────────────────
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

    // Fetch file content when activeFile changes
    useEffect(() => {
        if (!activeFile || !projectId) return
        const fetchContent = async () => {
            const token = getAuthToken()
            if (!token) return
            try {
                const res = await fetch(`${BACKEND_URL}/api/projects/${projectId}/files/read?file_path=${encodeURIComponent(activeFile)}`, {
                    headers: { Authorization: `Bearer ${token}` }
                })
                if (res.ok) {
                    const data = await res.json()
                    if (data.success && data.content !== undefined) {
                        setFileContent(data.content)
                        setSaveStatus("idle")
                    }
                }
            } catch (err) {}
        }
        fetchContent()
    }, [activeFile, projectId])

    // ── File selection handler ─────────────────────────────────────────────────
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

    const saveDebounceRef = useRef(null)
    // Autosave when fileContent changes
    useEffect(() => {
        if (!activeFile || !projectId) return
        
        clearTimeout(saveDebounceRef.current)
        saveDebounceRef.current = setTimeout(async () => {
            setSaveStatus("saving")
            const token = getAuthToken()
            if (!token) return
            try {
                const res = await fetch(`${BACKEND_URL}/api/projects/${projectId}/files/save`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
                    body: JSON.stringify({ file_path: activeFile, content: fileContent })
                })
                if (res.ok) {
                    const data = await res.json()
                    if (data.success) {
                        setSaveStatus("saved")
                        handleSave()
                    } else {
                        setSaveStatus("error")
                    }
                } else {
                    setSaveStatus("error")
                }
            } catch (err) {
                setSaveStatus("error")
            }
        }, 1500)
        return () => clearTimeout(saveDebounceRef.current)
    }, [fileContent, activeFile, projectId])

    // ── GitHub push handler ────────────────────────────────────────────────────
    const handleGithubSubmit = async () => {
        setGithubStatus({ state: "pushing", message: "Pushing to GitHub…", links: null })
        const code = fileContent
        try {
            const pushRes = await fetch("/api/github", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    action: "push",
                    token: githubForm.token,
                    owner: githubForm.owner,
                    repo: githubForm.repo,
                    branch: githubForm.branch,
                    baseBranch: githubForm.baseBranch,
                    filePath: githubForm.filePath,
                    content: code,
                    commitMessage: githubForm.commitMessage,
                }),
            })
            const pushData = await pushRes.json()
            if (!pushRes.ok) {
                setGithubStatus({ state: "error", message: pushData.error, links: null })
                return
            }

            if (!githubForm.createPR) {
                setGithubStatus({
                    state: "success",
                    message: `Pushed successfully! Commit: ${pushData.commit.slice(0, 7)}`,
                    links: { file: pushData.fileUrl },
                })
                return
            }

            setGithubStatus({ state: "creating-pr", message: "Creating pull request…", links: null })
            const prRes = await fetch("/api/github", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    action: "pr",
                    token: githubForm.token,
                    owner: githubForm.owner,
                    repo: githubForm.repo,
                    branch: githubForm.branch,
                    baseBranch: githubForm.baseBranch,
                    prTitle: githubForm.prTitle,
                    prBody: githubForm.prBody,
                }),
            })
            const prData = await prRes.json()
            if (!prRes.ok) {
                setGithubStatus({ state: "error", message: prData.error, links: null })
                return
            }
            setGithubStatus({
                state: "success",
                message: `PR #${prData.prNumber} created!`,
                links: { file: pushData.fileUrl, pr: prData.prUrl },
            })
        } catch {
            setGithubStatus({ state: "error", message: "Network error. Please try again.", links: null })
        }
    }

    // ── Deploy handler ─────────────────────────────────────────────────────────
    const handleDeploy = async () => {
        try {
            setIsDeploying(true)
            const connected = await isConnected()
            if (!connected) {
                alert("Please install and unlock Freighter extension.")
                return
            }

            const publicKey = await getPublicKey()
            if (!publicKey) return

            const uploadPrep = await fetch("/api/soroban/prepare-upload", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id: 1,
                    wasm_path: "target/wasm32-unknown-unknown/release/contract.wasm",
                    public_key: publicKey,
                }),
            }).then(r => r.json())

            if (!uploadPrep.success) throw new Error(uploadPrep.error)

            const signedUpload = await signTransaction(uploadPrep.unsigned_xdr, { network: "TESTNET" })

            const uploadResult = await fetch("/api/soroban/submit-tx", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ signed_xdr: signedUpload }),
            }).then(r => r.json())

            if (!uploadResult.success) throw new Error(uploadResult.error)
            const wasmHash = uploadResult.wasm_hash

            const createPrep = await fetch("/api/soroban/prepare-create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id: 1,
                    wasm_hash: wasmHash,
                    public_key: publicKey,
                }),
            }).then(r => r.json())

            if (!createPrep.success) throw new Error(createPrep.error)

            const signedCreate = await signTransaction(createPrep.unsigned_xdr, { network: "TESTNET" })

            const createResult = await fetch("/api/soroban/submit-tx", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ signed_xdr: signedCreate }),
            }).then(r => r.json())

            if (!createResult.success) throw new Error(createResult.error)

            setContractId(createResult.contract_id)
            alert(`Contract deployed successfully! ID: ${createResult.contract_id}`)
        } catch (error) {
            console.error("Deployment failed:", error)
            alert(`Deployment failed: ${error.message}`)
        } finally {
            setIsDeploying(false)
        }
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
                            assistantBuffer += event.data
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

    // ── Auth loading screen ────────────────────────────────────────────────────
    if (authLoading) {
        return (
            <div className="flex h-screen items-center justify-center bg-[#0D1117]">
                <div className="flex flex-col items-center gap-4">
                    <div className="w-8 h-8 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
                    <span className="text-gray-400 text-sm">Authenticating…</span>
                </div>
            </div>
        )
    }

    // ── Animation variants ─────────────────────────────────────────────────────
    const sidebarVariants = {
        open:   { x: 0,       opacity: 1 },
        closed: { x: "-100%", opacity: 0 },
    }

    const chatVariants = {
        open:   { x: 0,      opacity: 1 },
        closed: { x: "100%", opacity: 0 },
    }

    const closeAllOverlays = () => {
        setSidebarOpen(false)
        setChatOpen(false)
    }

    // ── Render ─────────────────────────────────────────────────────────────────
    return (
        <div className="flex h-[100dvh] bg-[#0D1117] text-white overflow-hidden">

            {/* Mobile backdrop */}
            <AnimatePresence>
                {isMobile && (sidebarOpen || chatOpen) && (
                    <motion.div
                        key="backdrop"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/60 z-30 md:hidden touch-none"
                        onClick={closeAllOverlays}
                        aria-hidden="true"
                    />
                )}
            </AnimatePresence>

            {/* Sidebar */}
            <AnimatePresence>
                {(sidebarOpen || !isMobile) && (
                    <motion.aside
                        key="sidebar"
                        initial={isMobile ? "closed" : false}
                        animate="open"
                        exit="closed"
                        variants={sidebarVariants}
                        transition={{ duration: 0.25, ease: "easeInOut" }}
                        aria-label="File Explorer"
                        className={[
                            "bg-[#161B22] border-r border-gray-700 flex flex-col shrink-0",
                            isMobile
                                ? "fixed left-0 top-0 h-full z-40 w-72 max-w-[80vw] shadow-2xl"
                                : sidebarOpen
                                    ? "relative w-64 lg:w-72"
                                    : "relative w-0 overflow-hidden",
                        ].join(" ")}
                    >
                        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700 min-h-[48px]">
                            <div className="flex gap-1">
                                <button
                                    onClick={() => setSidebarTab("explorer")}
                                    className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                                        sidebarTab === "explorer"
                                            ? "bg-gray-700 text-white"
                                            : "text-gray-400 hover:text-white"
                                    }`}
                                >
                                    <FolderOpen className="w-3 h-3" />
                                    Explorer
                                </button>
                                <button
                                    onClick={() => setSidebarTab("contract")}
                                    className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors ${
                                        sidebarTab === "contract"
                                            ? "bg-gray-700 text-white"
                                            : "text-gray-400 hover:text-white"
                                    }`}
                                >
                                    <Zap className="w-3 h-3" />
                                    Contract
                                </button>
                            </div>
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setSidebarOpen(false)}
                                aria-label="Close sidebar"
                                className="ml-2 shrink-0 h-8 w-8 p-0 text-gray-400 hover:text-white"
                            >
                                <X className="w-4 h-4" />
                            </Button>
                        </div>

                        <div className="flex-1 overflow-y-auto">
                            {sidebarTab === "explorer" && (
                                <FileExplorer
                                    projectId={projectId}
                                    onFileSelect={(node) => setActiveFile(node.path)}
                                    selectedPath={activeFile}
                                    className="h-full"
                                />
                            )}

                            {sidebarTab === "contract" && (
                                <ContractInteraction
                                    sessionId={null}
                                    authToken={null}
                                />
                            )}
                        </div>

                        <div className="p-3 border-t border-gray-700">
                            <Button
                                variant="ghost"
                                size="sm"
                                className="w-full justify-start gap-2 text-gray-400 hover:text-white h-9 px-2"
                            >
                                <Settings className="w-4 h-4 shrink-0" />
                                <span className="truncate">Settings</span>
                            </Button>
                        </div>
                    </motion.aside>
                )}
            </AnimatePresence>

            {/* Main content */}
            <div className="flex-1 flex flex-col min-w-0 overflow-hidden">

                {/* Toolbar */}
                <div className="h-12 bg-[#161B22] border-b border-gray-700 flex items-center px-3 gap-2 shrink-0">
                    <div className="flex items-center gap-2 min-w-0">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSidebarOpen(!sidebarOpen)}
                            aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"}
                            className="h-8 w-8 p-0 shrink-0 text-gray-400 hover:text-white"
                        >
                            {sidebarOpen && !isMobile
                                ? <ChevronLeft className="w-4 h-4" />
                                : <Menu className="w-4 h-4" />
                            }
                        </Button>
                        <span className="text-sm text-gray-400 truncate">
                            {activeFile ? activeFile.split("/").pop() : "contract.rs"}
                        </span>
                    </div>

                    {/* Context status indicator (from PR #61) */}
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

                    <div className="flex items-center gap-1 shrink-0">
                        <div className="hidden sm:inline-flex items-center px-2 text-xs text-gray-400">
                            {saveStatus === "saving" && <span className="animate-pulse">Saving...</span>}
                            {saveStatus === "saved" && <span className="text-green-500">Saved</span>}
                            {saveStatus === "error" && <span className="text-red-500">Error saving</span>}
                        </div>
                        {/* Save — desktop label, calls handleSave for context invalidation */}
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleSave}
                            className="hidden sm:inline-flex items-center gap-1 h-8 px-2 text-gray-400 hover:text-white"
                        >
                            <Save className="w-4 h-4" />
                            <span className="text-xs">Save</span>
                        </Button>
                        {/* Mobile icon-only */}
                        <Button
                            variant="ghost"
                            size="sm"
                            className="hidden sm:inline-flex items-center gap-1 h-8 px-2 text-gray-400 hover:text-white"
                        >
                            <Play className="w-4 h-4" />
                            <span className="text-xs">Run</span>
                        </Button>
                        {/* Save / Run — mobile icon-only */}
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleSave}
                            aria-label="Save"
                            className="sm:hidden h-8 w-8 p-0 text-gray-400 hover:text-white"
                        >
                            <Save className="w-4 h-4" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            aria-label="Run"
                            className="sm:hidden h-8 w-8 p-0 text-gray-400 hover:text-white"
                        >
                            <Play className="w-4 h-4" />
                        </Button>
                        {/* GitHub push — desktop */}
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => { setGithubStatus({ state: "idle", message: "", links: null }); setGithubModalOpen(true) }}
                            className="hidden sm:inline-flex items-center gap-1 h-8 px-2 text-gray-400 hover:text-white"
                            aria-label="Push to GitHub"
                        >
                            <Github className="w-4 h-4" />
                            <span className="text-xs">Push</span>
                        </Button>
                        {/* GitHub push — mobile */}
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => { setGithubStatus({ state: "idle", message: "", links: null }); setGithubModalOpen(true) }}
                            aria-label="Push to GitHub"
                            className="sm:hidden h-8 w-8 p-0 text-gray-400 hover:text-white"
                        >
                            <Github className="w-4 h-4" />
                        </Button>
                        {/* Deploy */}
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleDeploy}
                            disabled={isDeploying}
                            className={`hidden sm:flex p-1 h-auto ${isDeploying ? "text-blue-500 animate-pulse" : "text-gray-400 hover:text-white"}`}
                        >
                            <Rocket className="w-4 h-4 mr-1" />
                            {isDeploying ? "Deploying..." : "Deploy"}
                        </Button>
                        {/* Chat toggle */}
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setChatOpen(!chatOpen)}
                            aria-label={chatOpen ? "Close chat" : "Open chat"}
                            className="h-8 w-8 p-0 text-gray-400 hover:text-white"
                        >
                            <MessageSquare className="w-4 h-4" />
                        </Button>

                        {/* User menu */}
                        <div className="relative">
                            <button
                                onClick={() => setUserMenuOpen(o => !o)}
                                className="flex items-center gap-2 ml-2 focus:outline-none"
                                aria-label="User menu"
                            >
                                {user?.avatar_url ? (
                                    <img
                                        src={user.avatar_url}
                                        alt={user.username}
                                        className="w-7 h-7 rounded-full border border-gray-600 object-cover"
                                    />
                                ) : (
                                    <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-xs font-semibold">
                                        {user?.username?.[0]?.toUpperCase() ?? "?"}
                                    </div>
                                )}
                            </button>

                            <AnimatePresence>
                                {userMenuOpen && (
                                    <motion.div
                                        initial={{ opacity: 0, y: -6 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, y: -6 }}
                                        transition={{ duration: 0.15 }}
                                        className="absolute right-0 top-10 w-52 bg-[#1e2a38] border border-gray-700 rounded-lg shadow-xl z-50 overflow-hidden"
                                    >
                                        <div className="px-4 py-3 border-b border-gray-700">
                                            <p className="text-sm font-medium truncate">{user?.full_name || user?.username}</p>
                                            <p className="text-xs text-gray-400 truncate">{user?.email}</p>
                                            {user?.oauth_provider && (
                                                <span className="mt-1 inline-block text-[10px] px-1.5 py-0.5 rounded bg-gray-700 text-gray-300 capitalize">
                                                    via {user.oauth_provider}
                                                </span>
                                            )}
                                        </div>
                                        <button
                                            className="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-300 hover:bg-gray-700 transition-colors"
                                            onClick={() => { setUserMenuOpen(false) }}
                                        >
                                            <User className="w-4 h-4" /> Profile
                                        </button>
                                        <button
                                            className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-400 hover:bg-gray-700 transition-colors"
                                            onClick={() => { setUserMenuOpen(false); logout() }}
                                        >
                                            <LogOut className="w-4 h-4" /> Sign out
                                        </button>
                                    </motion.div>
                                )}
                            </AnimatePresence>
                        </div>
                    </div>
                </div>

                {/* Editor + Chat */}
                <div className="flex-1 flex overflow-hidden min-h-0">

                    {/* Code editor */}
                    <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                        <div className="flex-1 bg-[#0D1117] relative flex flex-col">
                            <textarea
                                value={fileContent}
                                onChange={(e) => setFileContent(e.target.value)}
                                spellCheck={false}
                                className="flex-1 w-full bg-transparent text-gray-200 font-mono text-sm leading-6 p-4 resize-none focus:outline-none placeholder-gray-600"
                                placeholder={activeFile ? `Editing ${activeFile.split('/').pop()}` : "Select a file to edit"}
                                disabled={!activeFile}
                            />
                        </div>
                    </div>

                    {/* Chat panel */}
                    <AnimatePresence>
                        {(chatOpen || !isMobile) && (
                            <motion.div
                                key="chat"
                                initial={isMobile ? "closed" : false}
                                animate="open"
                                exit="closed"
                                variants={chatVariants}
                                transition={{ duration: 0.25, ease: "easeInOut" }}
                                aria-label="AI Chat"
                                className={[
                                    "bg-[#161B22] border-l border-gray-700 flex flex-col shrink-0",
                                    isMobile
                                        ? "fixed right-0 top-0 h-full z-40 w-80 max-w-[88vw] shadow-2xl"
                                        : chatOpen
                                            ? "relative w-80 lg:w-96"
                                            : "relative w-0 overflow-hidden",
                                ].join(" ")}
                            >
                                {/* Chat header */}
                                <div className="flex items-center justify-between px-4 border-b border-gray-700 min-h-[48px] shrink-0">
                                    <div className="flex flex-col">
                                        <h3 className="text-sm font-semibold truncate">AI Assistant</h3>
                                        {contextSummary?.current_file && (
                                            <span className="text-[10px] text-gray-500 truncate max-w-[180px]">
                                                {contextSummary.current_file}
                                            </span>
                                        )}
                                    </div>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setChatOpen(false)}
                                        aria-label="Close chat"
                                        className="ml-2 shrink-0 h-8 w-8 p-0 text-gray-400 hover:text-white"
                                    >
                                        <X className="w-4 h-4" />
                                    </Button>
                                </div>

                                {/* Messages */}
                                <div
                                    ref={chatMessagesRef}
                                    className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0"
                                >
                                    {chatHistory.map((msg, idx) => (
                                        <div
                                            key={idx}
                                            className={`p-3 rounded-lg text-sm break-words ${
                                                msg.role === "user"
                                                    ? "bg-blue-600 ml-auto max-w-[85%] whitespace-pre-wrap"
                                                    : "bg-[#0D1117] max-w-full text-gray-200"
                                            }`}
                                        >
                                            {msg.role === "user" ? (
                                                <p className="leading-relaxed">{msg.content}</p>
                                            ) : (
                                                <div className="react-markdown-wrapper space-y-2">
                                                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                    <div ref={chatBottomRef} />
                                </div>

                                {/* Input */}
                                <div className="p-3 border-t border-gray-700 shrink-0 pb-[env(safe-area-inset-bottom,12px)]">
                                    <div className="flex items-end gap-2">
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
                                            aria-label="Chat message input"
                                            disabled={isSending}
                                            className="flex-1 min-w-0 bg-[#0D1117] border border-gray-600 rounded-lg px-3 py-2 text-sm leading-5 focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[40px] placeholder-gray-500 disabled:opacity-50"
                                            style={{ fontSize: "16px" }}
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
                                            aria-label="Send message"
                                            disabled={isSending || !message.trim()}
                                            className="shrink-0 h-10 w-10 p-0 text-gray-400 hover:text-white disabled:opacity-40"
                                            onClick={sendMessage}
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

            {/* GitHub modal */}
            <AnimatePresence>
                {githubModalOpen && (
                    <motion.div
                        key="github-modal-backdrop"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4"
                        onClick={(e) => { if (e.target === e.currentTarget) setGithubModalOpen(false) }}
                        aria-modal="true"
                        role="dialog"
                        aria-label="Push to GitHub"
                    >
                        <motion.div
                            initial={{ scale: 0.95, opacity: 0 }}
                            animate={{ scale: 1, opacity: 1 }}
                            exit={{ scale: 0.95, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="bg-[#161B22] border border-gray-700 rounded-xl w-full max-w-md shadow-2xl overflow-y-auto max-h-[90dvh]"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-700">
                                <div className="flex items-center gap-2">
                                    <Github className="w-5 h-5 text-white" />
                                    <h2 className="text-sm font-semibold">Push to GitHub</h2>
                                </div>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setGithubModalOpen(false)}
                                    aria-label="Close"
                                    className="h-8 w-8 p-0 text-gray-400 hover:text-white"
                                >
                                    <X className="w-4 h-4" />
                                </Button>
                            </div>

                            <div className="p-5 space-y-4">
                                <div>
                                    <label className="block text-xs text-gray-400 mb-1.5">GitHub Personal Access Token</label>
                                    <input
                                        type="password"
                                        value={githubForm.token}
                                        onChange={(e) => setGithubForm((f) => ({ ...f, token: e.target.value }))}
                                        placeholder="ghp_xxxxxxxxxxxx"
                                        className="w-full bg-[#0D1117] border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-600"
                                        autoComplete="off"
                                    />
                                    <p className="text-xs text-gray-500 mt-1">
                                        Requires <code className="text-gray-400">contents:write</code> and <code className="text-gray-400">pull_requests:write</code> scopes.
                                    </p>
                                </div>

                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <label className="block text-xs text-gray-400 mb-1.5">Owner</label>
                                        <input
                                            type="text"
                                            value={githubForm.owner}
                                            onChange={(e) => setGithubForm((f) => ({ ...f, owner: e.target.value.trim() }))}
                                            placeholder="your-username"
                                            className="w-full bg-[#0D1117] border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-600"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs text-gray-400 mb-1.5">Repository</label>
                                        <input
                                            type="text"
                                            value={githubForm.repo}
                                            onChange={(e) => setGithubForm((f) => ({ ...f, repo: e.target.value.trim() }))}
                                            placeholder="my-repo"
                                            className="w-full bg-[#0D1117] border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-600"
                                        />
                                    </div>
                                </div>

                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <label className="block text-xs text-gray-400 mb-1.5">Push to branch</label>
                                        <input
                                            type="text"
                                            value={githubForm.branch}
                                            onChange={(e) => setGithubForm((f) => ({ ...f, branch: e.target.value.trim() }))}
                                            placeholder="feature/my-branch"
                                            className="w-full bg-[#0D1117] border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-600"
                                        />
                                    </div>
                                    <div>
                                        <label className="block text-xs text-gray-400 mb-1.5">Base branch</label>
                                        <input
                                            type="text"
                                            value={githubForm.baseBranch}
                                            onChange={(e) => setGithubForm((f) => ({ ...f, baseBranch: e.target.value.trim() }))}
                                            placeholder="main"
                                            className="w-full bg-[#0D1117] border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-600"
                                        />
                                    </div>
                                </div>

                                <div>
                                    <label className="block text-xs text-gray-400 mb-1.5">File path in repo</label>
                                    <input
                                        type="text"
                                        value={githubForm.filePath}
                                        onChange={(e) => setGithubForm((f) => ({ ...f, filePath: e.target.value.trim() }))}
                                        placeholder="src/contract.rs"
                                        className="w-full bg-[#0D1117] border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-600"
                                    />
                                </div>

                                <div>
                                    <label className="block text-xs text-gray-400 mb-1.5">Commit message</label>
                                    <input
                                        type="text"
                                        value={githubForm.commitMessage}
                                        onChange={(e) => setGithubForm((f) => ({ ...f, commitMessage: e.target.value }))}
                                        placeholder="Update contract from CalliopeIDE"
                                        className="w-full bg-[#0D1117] border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-600"
                                    />
                                </div>

                                <label className="flex items-center gap-2 cursor-pointer select-none">
                                    <input
                                        type="checkbox"
                                        checked={githubForm.createPR}
                                        onChange={(e) => setGithubForm((f) => ({ ...f, createPR: e.target.checked }))}
                                        className="w-4 h-4 rounded accent-blue-500"
                                    />
                                    <span className="text-sm flex items-center gap-1.5">
                                        <GitPullRequest className="w-4 h-4 text-gray-400" />
                                        Create a Pull Request after push
                                    </span>
                                </label>

                                {githubForm.createPR && (
                                    <div className="space-y-3 pl-3 border-l-2 border-blue-600">
                                        <div>
                                            <label className="block text-xs text-gray-400 mb-1.5">PR Title</label>
                                            <input
                                                type="text"
                                                value={githubForm.prTitle}
                                                onChange={(e) => setGithubForm((f) => ({ ...f, prTitle: e.target.value }))}
                                                placeholder="Update smart contract"
                                                className="w-full bg-[#0D1117] border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-600"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs text-gray-400 mb-1.5">PR Description (optional)</label>
                                            <textarea
                                                value={githubForm.prBody}
                                                onChange={(e) => setGithubForm((f) => ({ ...f, prBody: e.target.value }))}
                                                placeholder="Describe your changes…"
                                                rows={3}
                                                className="w-full bg-[#0D1117] border border-gray-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-600 resize-none"
                                            />
                                        </div>
                                    </div>
                                )}

                                {githubStatus.state !== "idle" && (
                                    <div
                                        className={[
                                            "rounded-lg px-4 py-3 text-sm",
                                            githubStatus.state === "error"
                                                ? "bg-red-900/40 border border-red-700 text-red-300"
                                                : githubStatus.state === "success"
                                                ? "bg-green-900/40 border border-green-700 text-green-300"
                                                : "bg-blue-900/40 border border-blue-700 text-blue-300",
                                        ].join(" ")}
                                    >
                                        <p>{githubStatus.message}</p>
                                        {githubStatus.links && (
                                            <div className="mt-2 flex flex-col gap-1">
                                                {githubStatus.links.file && (
                                                    <a href={githubStatus.links.file} target="_blank" rel="noopener noreferrer" className="underline text-xs">
                                                        View file on GitHub ↗
                                                    </a>
                                                )}
                                                {githubStatus.links.pr && (
                                                    <a href={githubStatus.links.pr} target="_blank" rel="noopener noreferrer" className="underline text-xs">
                                                        View Pull Request ↗
                                                    </a>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>

                            <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-gray-700">
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => setGithubModalOpen(false)}
                                    className="text-gray-400 hover:text-white"
                                >
                                    Cancel
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={handleGithubSubmit}
                                    disabled={["pushing", "creating-pr"].includes(githubStatus.state)}
                                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 flex items-center gap-1.5 disabled:opacity-50"
                                >
                                    <Github className="w-4 h-4" />
                                    {githubStatus.state === "pushing"
                                        ? "Pushing…"
                                        : githubStatus.state === "creating-pr"
                                        ? "Creating PR…"
                                        : githubForm.createPR
                                        ? "Push & Create PR"
                                        : "Push"}
                                </Button>
                            </div>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}