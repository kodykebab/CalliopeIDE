"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/router"
import Link from "next/link"
import { motion, AnimatePresence } from "framer-motion"
import { Terminal, ArrowRight, Eye, EyeOff } from "lucide-react"
import { Button } from "@/components/ui/button"
import { GradientBackground } from "@/components/gradient-background"
import OAuthButtons from "@/components/auth/OAuthButtons"

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000"

export default function LoginPage() {
    const router = useRouter()

    const [tab, setTab]                   = useState("login")   // "login" | "register"
    const [email, setEmail]               = useState("")
    const [username, setUsername]         = useState("")
    const [password, setPassword]         = useState("")
    const [showPassword, setShowPassword] = useState(false)
    const [loading, setLoading]           = useState(false)
    const [error, setError]               = useState("")

    // Redirect if already authenticated
    useEffect(() => {
        if (localStorage.getItem("access_token")) {
            router.replace("/app")
        }
    }, [router])

    async function handleSubmit(e) {
        e.preventDefault()
        setLoading(true)
        setError("")

        const endpoint = tab === "login"
            ? `${BACKEND_URL}/api/auth/login`
            : `${BACKEND_URL}/api/auth/register`

        const body = tab === "login"
            ? { login: email, password }
            : { email, username, password }

        try {
            const res  = await fetch(endpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            })
            const data = await res.json()

            if (!res.ok) {
                setError(data.message || data.error || "Something went wrong.")
                return
            }

            localStorage.setItem("access_token",  data.access_token)
            localStorage.setItem("refresh_token", data.refresh_token)
            router.push("/app")
        } catch {
            setError("Network error — is the server running?")
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="flex flex-col min-h-screen bg-background text-foreground overflow-hidden transition-colors duration-300">
            <GradientBackground />

            {/* ── Minimal header ───────────────────────────────────────────── */}
            <header className="fixed top-0 left-0 right-0 z-50">
                <div className="mx-auto w-full flex h-16 sm:h-20 items-center justify-between px-4 sm:px-6 lg:px-8">
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.5 }}
                    >
                        <Link href="/" className="flex items-center gap-2">
                            <img src="/logo.svg" alt="Calliope" className="h-8 sm:h-[45px]" />
                        </Link>
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.5, delay: 0.2 }}
                        className="flex items-center gap-2 text-sm text-foreground/60"
                    >
                        {tab === "login" ? (
                            <>
                                <span>No account?</span>
                                <button
                                    onClick={() => { setTab("register"); setError("") }}
                                    className="text-[#9FEF00] hover:text-[#9FEF00]/80 font-medium transition-colors"
                                >
                                    Sign up
                                </button>
                            </>
                        ) : (
                            <>
                                <span>Have an account?</span>
                                <button
                                    onClick={() => { setTab("login"); setError("") }}
                                    className="text-[#9FEF00] hover:text-[#9FEF00]/80 font-medium transition-colors"
                                >
                                    Sign in
                                </button>
                            </>
                        )}
                    </motion.div>
                </div>
            </header>

            {/* ── Main ─────────────────────────────────────────────────────── */}
            <main className="flex-1 flex items-center justify-center px-4 sm:px-6 pt-24 pb-12">
                <div className="w-full max-w-md">

                    {/* Badge — same pattern as index.jsx hero badge */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5 }}
                        className="flex justify-center mb-6"
                    >
                        <div className="theme-panel inline-flex items-center px-3 py-1 rounded-full border text-sm">
                            <Terminal className="mr-2 h-4 w-4" />
                            Calliope IDE
                        </div>
                    </motion.div>

                    {/* Heading */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, delay: 0.08 }}
                        className="text-center mb-8"
                    >
                        <h1 className="text-3xl sm:text-4xl font-bold tracking-tight mb-2">
                            {tab === "login" ? "Welcome back" : "Create account"}
                        </h1>
                        <p className="text-foreground/60 text-sm">
                            {tab === "login"
                                ? "Sign in to continue building smart contracts"
                                : "Start building Soroban smart contracts today"}
                        </p>
                    </motion.div>

                    {/* Card — same theme-panel + rounded-xl + border + shadow as index.jsx */}
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.5, delay: 0.15 }}
                        className="theme-panel rounded-xl border backdrop-blur-sm shadow-2xl overflow-hidden"
                    >
                        {/* Tab switcher */}
                        <div className="flex border-b border-border/70">
                            {[
                                { key: "login",    label: "Sign in" },
                                { key: "register", label: "Create account" },
                            ].map((t) => (
                                <button
                                    key={t.key}
                                    onClick={() => { setTab(t.key); setError("") }}
                                    className={`
                                        flex-1 py-3 text-sm font-medium transition-colors duration-200
                                        ${tab === t.key
                                            ? "text-foreground border-b-2 border-[#9FEF00]"
                                            : "text-foreground/50 hover:text-foreground/80"
                                        }
                                    `}
                                >
                                    {t.label}
                                </button>
                            ))}
                        </div>

                        <div className="p-6 space-y-5">

                            {/* OAuth buttons component */}
                            <OAuthButtons />

                            {/* Divider — same style as feature cards in index.jsx */}
                            <div className="flex items-center gap-3">
                                <div className="flex-1 h-px bg-border/70" />
                                <span className="text-xs text-foreground/40">or continue with email</span>
                                <div className="flex-1 h-px bg-border/70" />
                            </div>

                            {/* Error message */}
                            <AnimatePresence>
                                {error && (
                                    <motion.div
                                        initial={{ opacity: 0, height: 0 }}
                                        animate={{ opacity: 1, height: "auto" }}
                                        exit={{ opacity: 0, height: 0 }}
                                        className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400 overflow-hidden"
                                        role="alert"
                                        aria-live="polite"
                                    >
                                        {error}
                                    </motion.div>
                                )}
                            </AnimatePresence>

                            {/* Form */}
                            <form onSubmit={handleSubmit} className="space-y-4">

                                {/* Email */}
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-foreground/50 uppercase tracking-wider">
                                        Email
                                    </label>
                                    <input
                                        type="email"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        placeholder="you@example.com"
                                        required
                                        autoComplete="email"
                                        className="theme-editor-surface w-full rounded-md border px-3 py-2.5 text-sm text-foreground placeholder:text-foreground/30 focus:border-[#9FEF00]/50 focus:ring-1 focus:ring-[#9FEF00]/30 focus-visible:outline-none transition-all duration-200"
                                    />
                                </div>

                                {/* Username — animated in/out for register tab */}
                                <AnimatePresence>
                                    {tab === "register" && (
                                        <motion.div
                                            initial={{ opacity: 0, height: 0 }}
                                            animate={{ opacity: 1, height: "auto" }}
                                            exit={{ opacity: 0, height: 0 }}
                                            className="space-y-1.5 overflow-hidden"
                                        >
                                            <label className="text-xs font-medium text-foreground/50 uppercase tracking-wider">
                                                Username
                                            </label>
                                            <input
                                                type="text"
                                                value={username}
                                                onChange={(e) => setUsername(e.target.value)}
                                                placeholder="soroban_dev"
                                                required={tab === "register"}
                                                autoComplete="username"
                                                className="theme-editor-surface w-full rounded-md border px-3 py-2.5 text-sm text-foreground placeholder:text-foreground/30 focus:border-[#9FEF00]/50 focus:ring-1 focus:ring-[#9FEF00]/30 focus-visible:outline-none transition-all duration-200"
                                            />
                                        </motion.div>
                                    )}
                                </AnimatePresence>

                                {/* Password */}
                                <div className="space-y-1.5">
                                    <label className="text-xs font-medium text-foreground/50 uppercase tracking-wider">
                                        Password
                                    </label>
                                    <div className="relative">
                                        <input
                                            type={showPassword ? "text" : "password"}
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            placeholder="••••••••"
                                            required
                                            autoComplete={tab === "login" ? "current-password" : "new-password"}
                                            className="theme-editor-surface w-full rounded-md border px-3 py-2.5 pr-10 text-sm text-foreground placeholder:text-foreground/30 focus:border-[#9FEF00]/50 focus:ring-1 focus:ring-[#9FEF00]/30 focus-visible:outline-none transition-all duration-200"
                                        />
                                        <button
                                            type="button"
                                            onClick={() => setShowPassword((s) => !s)}
                                            className="absolute right-3 top-1/2 -translate-y-1/2 text-foreground/40 hover:text-foreground/70 transition-colors"
                                            tabIndex={-1}
                                            aria-label={showPassword ? "Hide password" : "Show password"}
                                        >
                                            {showPassword
                                                ? <EyeOff className="w-4 h-4" />
                                                : <Eye    className="w-4 h-4" />
                                            }
                                        </button>
                                    </div>
                                </div>

                                {/* Submit — exact same Button style as index.jsx CTAs */}
                                <Button
                                    type="submit"
                                    disabled={loading}
                                    className="w-full h-10 bg-[#9FEF00] text-black hover:bg-[#9FEF00]/80 gap-2 group disabled:opacity-70 transition-colors"
                                >
                                    {loading ? (
                                        <span className="flex items-center gap-2">
                                            <span className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
                                            Please wait…
                                        </span>
                                    ) : (
                                        <>
                                            {tab === "login" ? "Sign in" : "Create account"}
                                            <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" />
                                        </>
                                    )}
                                </Button>
                            </form>
                        </div>
                    </motion.div>

                    {/* Footer note */}
                    <motion.p
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        transition={{ duration: 0.5, delay: 0.35 }}
                        className="text-center text-xs text-foreground/40 mt-6"
                    >
                        By continuing, you agree to our{" "}
                        <Link href="#" className="underline hover:text-foreground/60 transition-colors">Terms</Link>
                        {" "}and{" "}
                        <Link href="#" className="underline hover:text-foreground/60 transition-colors">Privacy Policy</Link>.
                    </motion.p>
                </div>
            </main>
        </div>
    )
}