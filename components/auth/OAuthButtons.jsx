/**
 * components/auth/OAuthButtons.jsx
 *
 * OAuth login buttons for GitHub and Google.
 * Uses Tailwind classes + project color tokens to match the existing UI.
 *
 * Usage:  <OAuthButtons />
 */

import { useState } from "react"
import { Github } from "lucide-react"
import { Button } from "@/components/ui/button"

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:5000"

export default function OAuthButtons() {
    const [loading, setLoading] = useState(null)  // 'github' | 'google' | null

    async function handleOAuth(provider) {
        setLoading(provider)
        try {
            const res  = await fetch(`${BACKEND_URL}/api/auth/oauth/${provider}`, {
                headers: { Accept: "application/json" },
            })
            const data = await res.json()

            if (!res.ok || !data.auth_url) {
                throw new Error(data.error || "OAuth not configured")
            }
            window.location.href = data.auth_url
        } catch (err) {
            alert(`Could not start ${provider} sign-in: ${err.message}`)
            setLoading(null)
        }
    }

    return (
        <div className="flex flex-col gap-3 w-full">
            {/* GitHub */}
            <Button
                type="button"
                variant="outline"
                disabled={!!loading}
                onClick={() => handleOAuth("github")}
                className="w-full h-10 border-border/80 text-foreground hover:bg-accent hover:border-border hover:text-accent-foreground gap-2 disabled:opacity-70 transition-colors"
                aria-label="Sign in with GitHub"
            >
                <Github className="size-4" />
                {loading === "github" ? "Redirecting…" : "Continue with GitHub"}
            </Button>

            {/* Google */}
            <Button
                type="button"
                variant="outline"
                disabled={!!loading}
                onClick={() => handleOAuth("google")}
                className="w-full h-10 border-border/80 text-foreground hover:bg-accent hover:border-border hover:text-accent-foreground gap-2 disabled:opacity-70 transition-colors"
                aria-label="Sign in with Google"
            >
                <GoogleIcon />
                {loading === "google" ? "Redirecting…" : "Continue with Google"}
            </Button>
        </div>
    )
}

function GoogleIcon() {
    return (
        <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" className="shrink-0">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
        </svg>
    )
}