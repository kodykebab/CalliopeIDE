"use client"

import { useState, useEffect, useRef } from "react"
import { useRouter } from "next/router"
import { motion, AnimatePresence } from "framer-motion"
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
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { getPublicKey, signTransaction, isConnected } from "@stellar/freighter-api"
import ContractInteraction from "@/components/ContractInteraction"

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000"

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

    const [user, setUser]               = useState(null)
    const [authLoading, setAuthLoading] = useState(true)

    const [sidebarOpen, setSidebarOpen]   = useState(true)
    const [chatOpen, setChatOpen]         = useState(true)
    const [message, setMessage]           = useState("")
    const [isMobile, setIsMobile]         = useState(false)
    const [userMenuOpen, setUserMenuOpen] = useState(false)
    const [isDeploying, setIsDeploying]   = useState(false)
    const [contractId, setContractId]     = useState(null)
    const [sidebarTab, setSidebarTab]     = useState("explorer")
    const chatMessagesRef = useRef(null)

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
            setAuthLoading(false)
        }
        init()
    }, [router])

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

    const handleGithubSubmit = async () => {
        setGithubStatus({ state: "pushing", message: "Pushing to GitHub…", links: null })
        const code = CODE_LINES.map((l) => l.code).join("\n")
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

    return (
        <div className="flex h-[100dvh] bg-[#0D1117] text-white overflow-hidden">
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
                                <div className="p-3 space-y-0.5">
                                    {[
                                        { icon: <FolderOpen className="w-4 h-4 text-blue-400 shrink-0" />, label: "src/",        indent: false },
                                        { icon: <span className="w-4 text-center text-xs shrink-0">📄</span>, label: "contract.rs", indent: true },
                                        { icon: <span className="w-4 text-center text-xs shrink-0">📄</span>, label: "lib.rs",      indent: true },
                                        { icon: <FolderOpen className="w-4 h-4 text-blue-400 shrink-0" />, label: "tests/",      indent: false },
                                        { icon: <span className="w-4 text-center text-xs shrink-0">📄</span>, label: "Cargo.toml", indent: false },
                                    ].map(({ icon, label, indent }) => (
                                        <div
                                            key={label}
                                            className={[
                                                "flex items-center gap-2 px-2 py-1.5 rounded hover:bg-gray-700 cursor-pointer transition-colors",
                                                indent ? "ml-4" : "",
                                            ].join(" ")}
                                        >
                                            {icon}
                                            <span className="text-sm truncate">{label}</span>
                                        </div>
                                    ))}
                                </div>
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

            <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
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
                        <span className="text-sm text-gray-400 truncate">contract.rs</span>
                    </div>

                    <div className="flex-1" />

                    <div className="flex items-center gap-1 shrink-0">
                        <Button
                            variant="ghost"
                            size="sm"
                            className="hidden sm:inline-flex items-center gap-1 h-8 px-2 text-gray-400 hover:text-white"
                        >
                            <Save className="w-4 h-4" />
                            <span className="text-xs">Save</span>
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
                            className="hidden sm:inline-flex items-center gap-1 h-8 px-2 text-gray-400 hover:text-white"
                        >
                            <Play className="w-4 h-4" />
                            <span className="text-xs">Run</span>
                        </Button>
                        <Button
                            variant="ghost"
                            size="sm"
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
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => { setGithubStatus({ state: "idle", message: "", links: null }); setGithubModalOpen(true) }}
                            aria-label="Push to GitHub"
                            className="sm:hidden h-8 w-8 p-0 text-gray-400 hover:text-white"
                        >
                            <Github className="w-4 h-4" />
                        </Button>
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
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setChatOpen(!chatOpen)}
                            aria-label={chatOpen ? "Close chat" : "Open chat"}
                            className="h-8 w-8 p-0 text-gray-400 hover:text-white"
                        >
                            <MessageSquare className="w-4 h-4" />
                        </Button>

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

                <div className="flex-1 flex overflow-hidden min-h-0">
                    <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                        <div className="flex-1 bg-[#0D1117] overflow-auto">
                            <div className="inline-grid min-w-full" style={{ gridTemplateColumns: "auto 1fr" }}>
                                <div
                                    className="select-none text-right pr-4 pl-4 py-4 text-gray-500 font-mono text-sm leading-6 border-r border-gray-800 bg-[#0D1117] sticky left-0"
                                    aria-hidden="true"
                                >
                                    {CODE_LINES.map(({ num }) => (
                                        <div key={num} className="leading-6">{num}</div>
                                    ))}
                                </div>
                                <div className="py-4 pl-4 pr-8 font-mono text-sm leading-6 text-gray-200 whitespace-pre overflow-x-auto">
                                    {CODE_LINES.map(({ num, code }) => (
                                        <div key={num} className="leading-6">{code || "\u00A0"}</div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>

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
                                <div className="flex items-center justify-between px-4 border-b border-gray-700 min-h-[48px] shrink-0">
                                    <h3 className="text-sm font-semibold truncate">AI Assistant</h3>
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

                                <div
                                    ref={chatMessagesRef}
                                    className="flex-1 overflow-y-auto p-4 space-y-3 min-h-0"
                                >
                                    <div className="bg-[#0D1117] p-3 rounded-lg max-w-[90%]">
                                        <p className="text-sm leading-relaxed">
                                            Hello{user ? `, ${user.full_name || user.username}` : ""}! I&apos;m your AI assistant for Soroban smart contract development. How can I help you today?
                                        </p>
                                    </div>

                                    <div className="bg-blue-600 p-3 rounded-lg ml-auto max-w-[85%]">
                                        <p className="text-sm leading-relaxed">Can you help me write a token contract?</p>
                                    </div>

                                    <div className="bg-[#0D1117] p-3 rounded-lg max-w-[90%]">
                                        <p className="text-sm leading-relaxed">
                                            Absolutely! I&apos;ll help you create a basic Soroban token contract. Let me start with the basic structure&hellip;
                                        </p>
                                    </div>
                                </div>

                                <div className="p-3 border-t border-gray-700 shrink-0 pb-[env(safe-area-inset-bottom,12px)]">
                                    <div className="flex items-end gap-2">
                                        <input
                                            type="text"
                                            value={message}
                                            onChange={(e) => setMessage(e.target.value)}
                                            placeholder="Ask about your code…"
                                            aria-label="Chat message input"
                                            className="flex-1 min-w-0 bg-[#0D1117] border border-gray-600 rounded-lg px-3 py-2 text-sm leading-5 focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[40px] placeholder-gray-500"
                                            style={{ fontSize: "16px" }}
                                            onKeyDown={(e) => {
                                                if (e.key === "Enter" && !e.shiftKey) {
                                                    e.preventDefault()
                                                    setMessage("")
                                                }
                                            }}
                                        />
                                        <Button
                                            variant="ghost"
                                            size="sm"
                                            aria-label="Send message"
                                            className="shrink-0 h-10 w-10 p-0 text-gray-400 hover:text-white"
                                            onClick={() => setMessage("")}
                                        >
                                            <Send className="w-4 h-4" />
                                        </Button>
                                    </div>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
            </div>

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