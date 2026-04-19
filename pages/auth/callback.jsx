import { useEffect, useState } from 'react'
import { useRouter } from 'next/router'
import Link from 'next/link'
import { GradientBackground } from '@/components/gradient-background'

export default function AuthCallback() {
  const router = useRouter()
  const [status, setStatus] = useState('Completing sign-in…')
  const [isError, setIsError] = useState(false)

useEffect(() => {
    if (!router.isReady) return

    const { code, error } = router.query   // ← code, not token/refresh

    if (error) {
        setIsError(true)
        setStatus(`Sign-in failed: ${decodeURIComponent(error)}`)
        setTimeout(() => router.replace('/login'), 3000)
        return
    }

    if (!code) {
        setIsError(true)
        setStatus('Invalid callback — missing code.')
        setTimeout(() => router.replace('/login'), 3000)
        return
    }

    fetch(`${BACKEND_URL}/api/auth/oauth/exchange`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
    })
        .then(r => r.json())
        .then(data => {
            if (!data.access_token) throw new Error(data.error || 'Exchange failed')
            localStorage.setItem('access_token',  data.access_token)
            localStorage.setItem('refresh_token', data.refresh_token)
            setStatus('Signed in! Redirecting…')
            router.replace('/app')
        })
        .catch(err => {
            setIsError(true)
            setStatus(err.message)
            setTimeout(() => router.replace('/login'), 3000)
        })
}, [router.isReady, router.query])

  return (
    <div className="flex flex-col min-h-screen bg-[#0D1117] text-white">
      <GradientBackground />

      {/* Logo — same header pattern as login.jsx */}
      <header className="fixed top-0 left-0 right-0 z-50 px-6 h-16 sm:h-20 flex items-center">
        <Link href="/">
          <img src="/logo.svg" alt="Calliope" className="h-8 sm:h-[45px]" />
        </Link>
      </header>

      <main className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          {isError ? (
            <>
              <div className="w-10 h-10 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center">
                <span className="text-red-400 text-lg">✕</span>
              </div>
              <p className="text-red-400 text-sm font-medium">{status}</p>
              <p className="text-gray-500 text-xs">Redirecting to login…</p>
            </>
          ) : (
            <>
              <div className="w-8 h-8 border-2 border-gray-600 border-t-blue-500 rounded-full animate-spin" />
              <p className="text-gray-400 text-sm">{status}</p>
            </>
          )}
        </div>
      </main>
    </div>
  )
}