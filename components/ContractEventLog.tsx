"use client"

import { useState } from "react"
import { Activity, RefreshCw, Filter, ChevronDown, ChevronUp, ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"

interface SorobanEvent {
  type: "CONTRACT" | "SYSTEM"
  contract_id: string | null
  topics: unknown[]
  data: unknown
  transaction_hash: string
  timestamp: string
  invoked_function: string
}

interface Props {
  sessionId: number
  authToken: string
  apiBaseUrl?: string
}

function TopicBadge({ value }: { value: unknown }) {
  const text = typeof value === "string" ? value : JSON.stringify(value)
  return (
    <span className="inline-block bg-blue-900/50 border border-blue-700 rounded px-1.5 py-0.5 font-mono text-[10px] text-blue-300">
      {text}
    </span>
  )
}

function EventCard({ event, index }: { event: SorobanEvent; index: number }) {
  const [open, setOpen] = useState(index === 0)

  const typeColor =
    event.type === "CONTRACT"
      ? "text-purple-300 bg-purple-900/30 border-purple-700"
      : "text-blue-300 bg-blue-900/30 border-blue-700"

  const explorerUrl = event.transaction_hash
    ? `https://stellar.expert/explorer/testnet/tx/${event.transaction_hash}`
    : null

  return (
    <div className="border border-gray-700 rounded overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 bg-[#0D1117] hover:bg-gray-900 text-xs text-left"
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className={`shrink-0 text-[10px] px-1.5 py-0.5 rounded border font-semibold ${typeColor}`}>
            {event.type}
          </span>
          <span className="font-mono text-gray-300 truncate">
            {event.topics.length > 0 ? JSON.stringify(event.topics[0]) : "(no topics)"}
          </span>
        </div>
        <div className="flex items-center gap-2 shrink-0 ml-2">
          <span className="text-gray-500 text-[10px]">
            {event.timestamp ? event.timestamp.slice(0, 19).replace("T", " ") : ""}
          </span>
          {open ? <ChevronUp className="w-3 h-3 text-gray-500" /> : <ChevronDown className="w-3 h-3 text-gray-500" />}
        </div>
      </button>

      {open && (
        <div className="px-3 py-2 border-t border-gray-700 flex flex-col gap-2 text-xs bg-[#080C10]">
          {event.contract_id && (
            <div>
              <span className="text-gray-500">Contract </span>
              <span className="font-mono text-gray-300 break-all">{event.contract_id}</span>
            </div>
          )}

          {event.invoked_function && (
            <div>
              <span className="text-gray-500">Via </span>
              <span className="font-mono text-blue-300">{event.invoked_function}()</span>
            </div>
          )}

          {event.topics.length > 0 && (
            <div>
              <p className="text-gray-500 mb-1">Topics</p>
              <div className="flex flex-wrap gap-1">
                {event.topics.map((t, i) => (
                  <TopicBadge key={i} value={t} />
                ))}
              </div>
            </div>
          )}

          {event.data !== null && event.data !== undefined && (
            <div>
              <p className="text-gray-500 mb-1">Data</p>
              <pre className="font-mono text-[11px] text-gray-200 whitespace-pre-wrap break-all bg-[#0D1117] rounded p-2">
                {JSON.stringify(event.data, null, 2)}
              </pre>
            </div>
          )}

          {explorerUrl && (
            <a
              href={explorerUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-blue-400 hover:text-blue-300 text-[10px] font-mono"
            >
              <ExternalLink className="w-3 h-3" />
              {event.transaction_hash.slice(0, 16)}…
            </a>
          )}
        </div>
      )}
    </div>
  )
}

export default function ContractEventLog({ sessionId, authToken, apiBaseUrl }: Props) {
  const base = apiBaseUrl || process.env.NEXT_PUBLIC_API_URL || ""

  const [events, setEvents] = useState<SorobanEvent[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [filterContract, setFilterContract] = useState("")
  const [filterActive, setFilterActive] = useState(false)

  const headers = { Authorization: `Bearer ${authToken}` }

  async function loadEvents(contractFilter?: string) {
    setLoading(true)
    setError(null)
    try {
      const qs = contractFilter ? `?contract_id=${encodeURIComponent(contractFilter)}` : ""
      const res = await fetch(`${base}/api/soroban/events/${sessionId}${qs}`, { headers })
      const data = await res.json()
      if (!res.ok || !data.success) {
        setError(data.error || "Failed to load events")
      } else {
        setEvents(data.events)
        setLoaded(true)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error")
    } finally {
      setLoading(false)
    }
  }

  function handleRefresh() {
    loadEvents(filterActive && filterContract ? filterContract : undefined)
  }

  function handleFilter(e: React.FormEvent) {
    e.preventDefault()
    const cf = filterContract.trim()
    setFilterActive(!!cf)
    loadEvents(cf || undefined)
  }

  function clearFilter() {
    setFilterContract("")
    setFilterActive(false)
    loadEvents()
  }

  return (
    <div className="flex flex-col gap-4 p-4 text-sm text-white">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
          <Activity className="w-3 h-3 text-purple-400" />
          Contract Events
          {loaded && (
            <span className="ml-1 text-[10px] text-gray-500 normal-case tracking-normal">
              ({events.length})
            </span>
          )}
        </h3>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={loading}
          className="text-gray-500 hover:text-white disabled:opacity-40"
          title="Refresh"
        >
          <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>

      <form onSubmit={handleFilter} className="flex gap-2">
        <input
          className={`${inputCls} flex-1`}
          placeholder="Filter by contract ID (optional)"
          value={filterContract}
          onChange={(e) => setFilterContract(e.target.value)}
        />
        <Button
          type="submit"
          disabled={loading}
          className="bg-gray-700 hover:bg-gray-600 text-white text-xs px-2.5 py-1.5 shrink-0 flex items-center gap-1"
        >
          <Filter className="w-3 h-3" />
          {filterActive ? "Refilter" : "Load"}
        </Button>
        {filterActive && (
          <Button
            type="button"
            onClick={clearFilter}
            className="bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs px-2.5 py-1.5 shrink-0"
          >
            Clear
          </Button>
        )}
      </form>

      {error && (
        <div className="p-2 bg-red-900/40 border border-red-700 rounded text-red-300 text-xs">
          {error}
        </div>
      )}

      {!loaded && !loading && (
        <p className="text-gray-500 text-xs">
          Load events to see contract activity from this session's invocations.
        </p>
      )}

      {loaded && events.length === 0 && (
        <p className="text-gray-500 text-xs">
          {filterActive
            ? "No events found for this contract."
            : "No contract events recorded yet. Invoke a contract to see its events here."}
        </p>
      )}

      {events.length > 0 && (
        <div className="flex flex-col gap-2">
          {events.map((event, i) => (
            <EventCard key={`${event.transaction_hash}-${i}`} event={event} index={i} />
          ))}
        </div>
      )}
    </div>
  )
}

const inputCls =
  "bg-[#0D1117] border border-gray-600 rounded px-2 py-1.5 text-xs text-white " +
  "placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-purple-500 w-full"
