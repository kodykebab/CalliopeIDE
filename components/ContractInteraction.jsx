"use client"

import { useState } from "react"
import { Play, RefreshCw, ChevronDown, ChevronUp, Clock, Database } from "lucide-react"
import { Button } from "@/components/ui/button"
import { getWalletPublicKey, signWithFreighter, NETWORKS } from "../lib/freighter"

/**
 * ContractInteraction — invoke contract functions and view ledger state.
 *
 * Props:
 *   sessionId   (number)  — active session ID
 *   authToken   (string)  — JWT bearer token
 *   apiBaseUrl  (string)  — base URL for the API (default: NEXT_PUBLIC_API_URL)
 */
export default function ContractInteraction({ sessionId, authToken, apiBaseUrl }) {
  const base = apiBaseUrl || process.env.NEXT_PUBLIC_API_URL || ""

  // ── invoke form state ──────────────────────────────────────────────────
  const [contractId, setContractId] = useState("")
  const [functionName, setFunctionName] = useState("")
  const [paramsRaw, setParamsRaw] = useState("")   // one param per line
  const [invoking, setInvoking] = useState(false)
  const [invokeResult, setInvokeResult] = useState(null)
  const [invokeError, setInvokeError] = useState(null)
  const [invokeStatus, setInvokeStatus] = useState("idle")  // idle, connecting, building, signing, submitting
  const [publicKey, setPublicKey] = useState("")

  // ── history state ──────────────────────────────────────────────────────
  const [history, setHistory] = useState([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)

  // ── state viewer ───────────────────────────────────────────────────────
  const [stateContractId, setStateContractId] = useState("")
  const [stateEntries, setStateEntries] = useState(null)
  const [stateLoading, setStateLoading] = useState(false)
  const [stateError, setStateError] = useState(null)

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${authToken}`,
  }

  // ── invoke ─────────────────────────────────────────────────────────────
  async function handleInvoke(e) {
    e.preventDefault()
    setInvoking(true)
    setInvokeResult(null)
    setInvokeError(null)
    setInvokeStatus("connecting")

    const parameters = paramsRaw
      .split("\n")
      .map((p) => p.trim())
      .filter(Boolean)

    try {
      // Step 1: Get public key from Freighter
      const userPublicKey = await getWalletPublicKey()
      setPublicKey(userPublicKey)

      // Step 2: Build unsigned transaction
      setInvokeStatus("building")
      const prepareRes = await fetch(`${base}/api/soroban/prepare-invoke`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          session_id: sessionId,
          contract_id: contractId.trim(),
          function_name: functionName.trim(),
          parameters,
          public_key: userPublicKey,
        }),
      })

      if (!prepareRes.ok) {
        const err = await prepareRes.json()
        throw new Error(err.error || "Failed to build transaction")
      }

      const { unsigned_xdr } = await prepareRes.json()

      // Step 3: Sign with Freighter (client-side, key never leaves browser)
      setInvokeStatus("signing")
      const signedXdr = await signWithFreighter(unsigned_xdr, NETWORKS.testnet)

      // Step 4: Submit signed transaction
      setInvokeStatus("submitting")
      const submitRes = await fetch(`${base}/api/soroban/submit-invoke`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          session_id: sessionId,
          signed_xdr: signedXdr,
          contract_id: contractId.trim(),
          function_name: functionName.trim(),
          parameters,
        }),
      })

      const data = await submitRes.json()
      if (!submitRes.ok || !data.success) {
        setInvokeError(data.error || "Invocation failed")
      } else {
        setInvokeResult(data)
      }
    } catch (err) {
      setInvokeError(err.message || "Network error")
    } finally {
      setInvoking(false)
      setInvokeStatus("idle")
    }
  }

  // ── history ────────────────────────────────────────────────────────────
  async function loadHistory() {
    setHistoryLoading(true)
    try {
      const res = await fetch(`${base}/api/soroban/invocations/${sessionId}`, { headers })
      const data = await res.json()
      if (data.success) setHistory(data.invocations)
    } catch (_) {
      // silently ignore
    } finally {
      setHistoryLoading(false)
    }
  }

  function toggleHistory() {
    if (!historyOpen) loadHistory()
    setHistoryOpen((v) => !v)
  }

  // ── state viewer ───────────────────────────────────────────────────────
  async function handleFetchState(e) {
    e.preventDefault()
    setStateLoading(true)
    setStateEntries(null)
    setStateError(null)
    try {
      const res = await fetch(
        `${base}/api/soroban/state/${sessionId}/${stateContractId.trim()}`,
        { headers }
      )
      const data = await res.json()
      if (!res.ok || !data.success) {
        setStateError(data.error || "Failed to fetch state")
      } else {
        setStateEntries(data.state_entries)
      }
    } catch (err) {
      setStateError(err.message || "Network error")
    } finally {
      setStateLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-6 p-4 text-sm text-white">

      {/* ── Invoke Form ─────────────────────────────────────────────── */}
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3 flex items-center gap-1">
          <Play className="w-3 h-3" /> Invoke Contract Function
        </h3>

        <form onSubmit={handleInvoke} className="flex flex-col gap-2">
          <input
            className={inputCls}
            placeholder="Contract ID (C...)"
            value={contractId}
            onChange={(e) => setContractId(e.target.value)}
            required
          />
          <input
            className={inputCls}
            placeholder="Function name"
            value={functionName}
            onChange={(e) => setFunctionName(e.target.value)}
            required
          />
          <textarea
            className={`${inputCls} resize-none`}
            rows={3}
            placeholder={"Parameters (one per line)\ne.g. u32:42\naddress:G...\nstr:hello"}
            value={paramsRaw}
            onChange={(e) => setParamsRaw(e.target.value)}
          />
          <Button
            type="submit"
            disabled={invoking}
            className="bg-blue-600 hover:bg-blue-700 text-white text-xs py-1.5"
          >
            {invokeStatus === "connecting" && "Connecting to Freighter..."}
            {invokeStatus === "building" && "Building transaction..."}
            {invokeStatus === "signing" && "Waiting for signature..."}
            {invokeStatus === "submitting" && "Submitting..."}
            {invokeStatus === "idle" && (invoking ? "Invoking..." : "Invoke with Freighter")}
          </Button>
        </form>

        {invokeError && (
          <div className="mt-2 p-2 bg-red-900/40 border border-red-700 rounded text-red-300 text-xs">
            {invokeError}
          </div>
        )}

        {invokeResult && (
          <div className="mt-2 p-2 bg-green-900/30 border border-green-700 rounded text-xs space-y-1">
            <div className="text-green-400 font-semibold">Success</div>
            <div>
              <span className="text-gray-400">Result: </span>
              <span className="font-mono">{JSON.stringify(invokeResult.result)}</span>
            </div>
            <div>
              <span className="text-gray-400">Tx: </span>
              <a
                href={invokeResult.explorer_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 underline font-mono break-all"
              >
                {invokeResult.transaction_hash}
              </a>
            </div>
          </div>
        )}
      </section>

      {/* ── State Viewer ────────────────────────────────────────────── */}
      <section>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-3 flex items-center gap-1">
          <Database className="w-3 h-3" /> Contract State
        </h3>

        <form onSubmit={handleFetchState} className="flex gap-2">
          <input
            className={`${inputCls} flex-1`}
            placeholder="Contract ID (C...)"
            value={stateContractId}
            onChange={(e) => setStateContractId(e.target.value)}
            required
          />
          <Button
            type="submit"
            disabled={stateLoading}
            className="bg-gray-700 hover:bg-gray-600 text-white text-xs px-3 py-1.5 shrink-0"
          >
            {stateLoading ? <RefreshCw className="w-3 h-3 animate-spin" /> : "Fetch"}
          </Button>
        </form>

        {stateError && (
          <div className="mt-2 p-2 bg-red-900/40 border border-red-700 rounded text-red-300 text-xs">
            {stateError}
          </div>
        )}

        {stateEntries !== null && (
          <div className="mt-2 border border-gray-700 rounded overflow-hidden">
            {stateEntries.length === 0 ? (
              <p className="p-2 text-gray-500 text-xs">No state entries found.</p>
            ) : (
              <table className="w-full text-xs">
                <thead className="bg-gray-800 text-gray-400">
                  <tr>
                    <th className="text-left px-2 py-1">Key</th>
                    <th className="text-left px-2 py-1">Value</th>
                    <th className="text-left px-2 py-1">Durability</th>
                  </tr>
                </thead>
                <tbody>
                  {stateEntries.map((entry, i) => (
                    <tr key={i} className="border-t border-gray-700 hover:bg-gray-800/50">
                      <td className="px-2 py-1 font-mono break-all">{JSON.stringify(entry.key)}</td>
                      <td className="px-2 py-1 font-mono break-all">{JSON.stringify(entry.value)}</td>
                      <td className="px-2 py-1 text-gray-400">{entry.durability}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </section>

      {/* ── Invocation History ──────────────────────────────────────── */}
      <section>
        <button
          type="button"
          onClick={toggleHistory}
          className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-gray-400 hover:text-white"
        >
          <Clock className="w-3 h-3" />
          Invocation History
          {historyOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>

        {historyOpen && (
          <div className="mt-2">
            {historyLoading ? (
              <p className="text-gray-500 text-xs">Loading…</p>
            ) : history.length === 0 ? (
              <p className="text-gray-500 text-xs">No invocations yet.</p>
            ) : (
              <div className="flex flex-col gap-2">
                {history.map((inv, i) => (
                  <div key={i} className="p-2 bg-[#0D1117] border border-gray-700 rounded text-xs space-y-0.5">
                    <div className="flex justify-between">
                      <span className="font-mono text-blue-300">{inv.function_name}</span>
                      <span className="text-gray-500">{inv.timestamp?.slice(0, 19).replace("T", " ")}</span>
                    </div>
                    <div className="text-gray-400 font-mono truncate">{inv.contract_id}</div>
                    <div>
                      <span className="text-gray-400">Result: </span>
                      <span className="font-mono">{JSON.stringify(inv.result)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  )
}

const inputCls =
  "bg-[#0D1117] border border-gray-600 rounded px-2 py-1.5 text-xs text-white " +
  "placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500 w-full"
