"use client"

import { useState } from "react"
import { Zap, ChevronDown, ChevronUp, AlertTriangle, CheckCircle2, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"

type Network = "testnet" | "mainnet"

interface FeeBreakdown {
  base_fee: number
  resource_fee: number
  total_stroops: number
  xlm: string
}

interface ResourceUsage {
  cpu_insns: number
  mem_bytes: number
  read_bytes: number
  write_bytes: number
}

interface SimulateInvokeResult {
  success: boolean
  fee: FeeBreakdown
  resources: ResourceUsage
  simulated_result: unknown
  auth_entries: string[]
  network: Network
  simulation_error: string | null
}

interface SimulateDeployResult {
  success: boolean
  upload_fee: FeeBreakdown & { resources: ResourceUsage }
  wasm_size_bytes: number
  network: Network
  note: string
}

interface Props {
  sessionId: number
  authToken: string
  apiBaseUrl?: string
  wasmPath?: string
  mode?: "invoke" | "deploy"
}

function ResourceRow({ label, value, unit }: { label: string; value: number; unit: string }) {
  return (
    <div className="flex justify-between text-xs">
      <span className="text-gray-400">{label}</span>
      <span className="font-mono text-gray-200">
        {value.toLocaleString()} {unit}
      </span>
    </div>
  )
}

function FeeRow({ label, stroops, highlight }: { label: string; stroops: number; highlight?: boolean }) {
  const xlm = (stroops / 10_000_000).toFixed(7)
  return (
    <div className={`flex justify-between text-xs ${highlight ? "font-semibold text-white" : "text-gray-300"}`}>
      <span className={highlight ? "" : "text-gray-400"}>{label}</span>
      <span className="font-mono">
        {stroops.toLocaleString()} stroops
        <span className="text-gray-500 ml-1">({xlm} XLM)</span>
      </span>
    </div>
  )
}

export default function SimulationPanel({
  sessionId,
  authToken,
  apiBaseUrl,
  wasmPath,
  mode = "invoke",
}: Props) {
  const base = apiBaseUrl || process.env.NEXT_PUBLIC_API_URL || ""

  const [contractId, setContractId] = useState("")
  const [functionName, setFunctionName] = useState("")
  const [invokerPublicKey, setInvokerPublicKey] = useState("")
  const [paramsRaw, setParamsRaw] = useState("")
  const [network, setNetwork] = useState<Network>("testnet")

  const [loading, setLoading] = useState(false)
  const [invokeResult, setInvokeResult] = useState<SimulateInvokeResult | null>(null)
  const [deployResult, setDeployResult] = useState<SimulateDeployResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [authOpen, setAuthOpen] = useState(false)

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${authToken}`,
  }

  async function handleSimulateInvoke(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setInvokeResult(null)
    setError(null)

    const parameters = paramsRaw
      .split("\n")
      .map((p) => p.trim())
      .filter(Boolean)

    try {
      const res = await fetch(`${base}/api/soroban/simulate/invoke`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          session_id: sessionId,
          contract_id: contractId.trim(),
          function_name: functionName.trim(),
          invoker_public_key: invokerPublicKey.trim(),
          parameters,
          network,
        }),
      })
      const data: SimulateInvokeResult = await res.json()
      if (!res.ok || !data.success) {
        setError((data as { error?: string }).error || "Simulation failed")
      } else {
        setInvokeResult(data)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error")
    } finally {
      setLoading(false)
    }
  }

  async function handleSimulateDeploy(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setDeployResult(null)
    setError(null)

    try {
      const res = await fetch(`${base}/api/soroban/simulate/deploy`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          session_id: sessionId,
          wasm_path: wasmPath,
          deployer_public_key: invokerPublicKey.trim(),
          network,
        }),
      })
      const data: SimulateDeployResult = await res.json()
      if (!res.ok || !data.success) {
        setError((data as { error?: string }).error || "Simulation failed")
      } else {
        setDeployResult(data)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error")
    } finally {
      setLoading(false)
    }
  }

  const result = mode === "invoke" ? invokeResult : deployResult

  return (
    <div className="flex flex-col gap-4 p-4 text-sm text-white">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
        <Zap className="w-3 h-3 text-yellow-400" />
        Pre-flight Simulation
      </h3>

      <form
        onSubmit={mode === "invoke" ? handleSimulateInvoke : handleSimulateDeploy}
        className="flex flex-col gap-2"
      >
        <select
          className={`${inputCls} bg-[#0D1117]`}
          value={network}
          onChange={(e) => setNetwork(e.target.value as Network)}
          disabled={loading}
        >
          <option value="testnet">Testnet</option>
          <option value="mainnet">Mainnet</option>
        </select>

        {mode === "invoke" && (
          <>
            <input
              className={inputCls}
              placeholder="Contract ID (C...)"
              value={contractId}
              onChange={(e) => setContractId(e.target.value)}
              disabled={loading}
              required
            />
            <input
              className={inputCls}
              placeholder="Function name"
              value={functionName}
              onChange={(e) => setFunctionName(e.target.value)}
              disabled={loading}
              required
            />
            <textarea
              className={`${inputCls} resize-none`}
              rows={3}
              placeholder={"Parameters (one per line)\ne.g. u32:42\naddress:G...\nbool:true"}
              value={paramsRaw}
              onChange={(e) => setParamsRaw(e.target.value)}
              disabled={loading}
            />
          </>
        )}

        <input
          className={inputCls}
          placeholder={mode === "invoke" ? "Invoker public key (G...)" : "Deployer public key (G...)"}
          value={invokerPublicKey}
          onChange={(e) => setInvokerPublicKey(e.target.value)}
          disabled={loading}
          required
        />

        <Button
          type="submit"
          disabled={loading}
          className="bg-yellow-600 hover:bg-yellow-700 text-white text-xs py-1.5"
        >
          {loading ? (
            <span className="flex items-center gap-1.5">
              <Loader2 className="w-3 h-3 animate-spin" />
              Simulating…
            </span>
          ) : (
            "Simulate"
          )}
        </Button>
      </form>

      {error && (
        <div className="p-2 bg-red-900/40 border border-red-700 rounded text-red-300 text-xs flex items-start gap-1.5">
          <AlertTriangle className="w-3 h-3 shrink-0 mt-0.5" />
          {error}
        </div>
      )}

      {invokeResult && mode === "invoke" && (
        <div className="flex flex-col gap-3 p-3 bg-[#0D1117] border border-gray-700 rounded text-xs">
          <div className="flex items-center gap-1.5 text-green-400 font-semibold">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Simulation successful
          </div>

          {invokeResult.simulation_error && (
            <div className="p-2 bg-yellow-900/40 border border-yellow-700 rounded text-yellow-300 text-xs">
              <p className="font-semibold mb-1">Contract would revert:</p>
              <pre className="whitespace-pre-wrap break-all overflow-auto max-h-32 font-mono text-[10px]">
                {invokeResult.simulation_error}
              </pre>
            </div>
          )}

          <div>
            <p className="text-gray-500 uppercase text-[10px] tracking-wider mb-1.5">Fee Estimate</p>
            <div className="flex flex-col gap-1">
              <FeeRow label="Base fee" stroops={invokeResult.fee.base_fee} />
              <FeeRow label="Resource fee" stroops={invokeResult.fee.resource_fee} />
              <div className="border-t border-gray-700 my-1" />
              <FeeRow label="Total" stroops={invokeResult.fee.total_stroops} highlight />
            </div>
          </div>

          <div>
            <p className="text-gray-500 uppercase text-[10px] tracking-wider mb-1.5">Resource Usage</p>
            <div className="flex flex-col gap-1">
              <ResourceRow label="CPU instructions" value={invokeResult.resources.cpu_insns} unit="" />
              <ResourceRow label="Memory" value={invokeResult.resources.mem_bytes} unit="bytes" />
              <ResourceRow label="Ledger reads" value={invokeResult.resources.read_bytes} unit="bytes" />
              <ResourceRow label="Ledger writes" value={invokeResult.resources.write_bytes} unit="bytes" />
            </div>
          </div>

          {invokeResult.simulated_result !== null && invokeResult.simulated_result !== undefined && (
            <div>
              <p className="text-gray-500 uppercase text-[10px] tracking-wider mb-1">Simulated Return Value</p>
              <pre className="font-mono text-green-300 text-[11px] whitespace-pre-wrap break-all">
                {JSON.stringify(invokeResult.simulated_result, null, 2)}
              </pre>
            </div>
          )}

          {invokeResult.auth_entries.length > 0 && (
            <div>
              <button
                type="button"
                className="flex items-center gap-1 text-gray-400 hover:text-white"
                onClick={() => setAuthOpen((v) => !v)}
              >
                Auth entries ({invokeResult.auth_entries.length})
                {authOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>
              {authOpen && (
                <div className="mt-1 flex flex-col gap-1">
                  {invokeResult.auth_entries.map((a, i) => (
                    <pre key={i} className="font-mono text-[10px] text-gray-400 break-all whitespace-pre-wrap">
                      {a}
                    </pre>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {deployResult && mode === "deploy" && (
        <div className="flex flex-col gap-3 p-3 bg-[#0D1117] border border-gray-700 rounded text-xs">
          <div className="flex items-center gap-1.5 text-green-400 font-semibold">
            <CheckCircle2 className="w-3.5 h-3.5" />
            Deploy simulation complete
          </div>

          <div>
            <p className="text-gray-500 uppercase text-[10px] tracking-wider mb-1.5">Upload Fee Estimate</p>
            <div className="flex flex-col gap-1">
              <FeeRow label="Base fee" stroops={deployResult.upload_fee.base_fee} />
              <FeeRow label="Resource fee" stroops={deployResult.upload_fee.resource_fee} />
              <div className="border-t border-gray-700 my-1" />
              <FeeRow label="Upload total" stroops={deployResult.upload_fee.total_stroops} highlight />
            </div>
          </div>

          <div>
            <p className="text-gray-500 uppercase text-[10px] tracking-wider mb-1.5">Resource Usage</p>
            <div className="flex flex-col gap-1">
              <ResourceRow label="CPU instructions" value={deployResult.upload_fee.resources.cpu_insns} unit="" />
              <ResourceRow label="Memory" value={deployResult.upload_fee.resources.mem_bytes} unit="bytes" />
              <ResourceRow label="Ledger reads" value={deployResult.upload_fee.resources.read_bytes} unit="bytes" />
              <ResourceRow label="Ledger writes" value={deployResult.upload_fee.resources.write_bytes} unit="bytes" />
            </div>
          </div>

          <div className="flex justify-between text-xs">
            <span className="text-gray-400">WASM size</span>
            <span className="font-mono text-gray-200">
              {(deployResult.wasm_size_bytes / 1024).toFixed(1)} KB
            </span>
          </div>

          <p className="text-gray-500 text-[10px] italic">{deployResult.note}</p>
        </div>
      )}
    </div>
  )
}

const inputCls =
  "bg-[#0D1117] border border-gray-600 rounded px-2 py-1.5 text-xs text-white " +
  "placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-yellow-500 w-full"
