import { useState } from "react";
import {
  getWalletPublicKey,
  signWithFreighter,
  NETWORKS,
} from "../lib/freighter";

const STATUS = {
  IDLE: "idle",
  CONNECTING: "connecting",
  BUILDING: "building",
  SIGNING: "signing",
  DEPLOYING: "deploying",
  SUCCESS: "success",
  ERROR: "error",
};

const STATUS_MESSAGES = {
  idle: "",
  connecting: "Connecting to Freighter...",
  building: "Building unsigned transaction...",
  signing: "Waiting for Freighter signature...",
  deploying: "Submitting to Stellar network...",
  success: "Contract deployed successfully!",
  error: "",
};

export default function DeployPanel({ sessionId, wasmPath, network = "testnet" }) {
  const [status, setStatus] = useState(STATUS.IDLE);
  const [contractId, setContractId] = useState(null);
  const [errorMsg, setErrorMsg] = useState("");
  const [fundAccount, setFundAccount] = useState(true);

  async function handleDeploy() {
    setStatus(STATUS.CONNECTING);
    setErrorMsg("");
    setContractId(null);

    try {
      // Step 1: get public key from Freighter
      const publicKey = await getWalletPublicKey();

      // Step 2: request unsigned XDR from backend
      setStatus(STATUS.BUILDING);
      const buildRes = await fetch("/api/soroban/build-deploy-tx", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          wasm_path: wasmPath,
          deployer_public_key: publicKey,
          fund_account: fundAccount,
          network,
        }),
      });

      if (!buildRes.ok) {
        const err = await buildRes.json();
        throw new Error(err.error || "Failed to build transaction");
      }

      const { unsigned_xdr } = await buildRes.json();

      // Step 3: sign with Freighter (client-side, key never leaves browser)
      setStatus(STATUS.SIGNING);
      const signedXdr = await signWithFreighter(
        unsigned_xdr,
        NETWORKS[network]
      );

      // Step 4: submit signed XDR
      setStatus(STATUS.DEPLOYING);
      const deployRes = await fetch("/api/soroban/submit-deploy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          signed_xdr: signedXdr,
          network,
        }),
      });

      if (!deployRes.ok) {
        const err = await deployRes.json();
        throw new Error(err.error || "Deployment failed");
      }

      const { contract_id } = await deployRes.json();
      setContractId(contract_id);
      setStatus(STATUS.SUCCESS);
    } catch (err) {
      setErrorMsg(err.message);
      setStatus(STATUS.ERROR);
    }
  }

  const isLoading = ![STATUS.IDLE, STATUS.SUCCESS, STATUS.ERROR].includes(status);

  return (
    <div style={{
      padding: "16px",
      border: "1px solid #2a2a2a",
      borderRadius: "8px",
      background: "#1a1a1a",
      color: "#e0e0e0",
      fontFamily: "monospace",
      fontSize: "13px",
    }}>
      <div style={{ fontWeight: 600, marginBottom: "12px", fontSize: "14px" }}>
        Deploy Contract
      </div>

      <label style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
        <input
          type="checkbox"
          checked={fundAccount}
          onChange={(e) => setFundAccount(e.target.checked)}
          disabled={isLoading}
        />
        Fund account via Friendbot (testnet only)
      </label>

      <button
        onClick={handleDeploy}
        disabled={isLoading}
        style={{
          padding: "8px 16px",
          background: isLoading ? "#333" : "#7c3aed",
          color: "#fff",
          border: "none",
          borderRadius: "6px",
          cursor: isLoading ? "not-allowed" : "pointer",
          fontSize: "13px",
          width: "100%",
        }}
      >
        {isLoading ? STATUS_MESSAGES[status] : "Deploy with Freighter"}
      </button>

      {status === STATUS.SUCCESS && contractId && (
        <div style={{ marginTop: "12px", color: "#4ade80" }}>
          ✓ Contract ID: <span style={{ wordBreak: "break-all" }}>{contractId}</span>
        </div>
      )}

      {status === STATUS.ERROR && (
        <div style={{ marginTop: "12px", color: "#f87171" }}>
          ✗ {errorMsg}
        </div>
      )}
    </div>
  );
}
