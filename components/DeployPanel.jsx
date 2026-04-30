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

export default function DeployPanel({ sessionId, wasmPath, authToken, network = "testnet" }) {
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

      // Step 2: Upload WASM
      setStatus(STATUS.BUILDING);
      const uploadRes = await fetch("/api/soroban/prepare-upload", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${authToken}` },
        body: JSON.stringify({
          session_id: sessionId,
          wasm_path: wasmPath,
          public_key: publicKey,
        }),
      });

      if (!uploadRes.ok) {
        const err = await uploadRes.json();
        throw new Error(err.error || "Failed to prepare upload transaction");
      }

      const { unsigned_xdr: uploadXdr } = await uploadRes.json();

      // Step 3: Sign upload transaction
      setStatus(STATUS.SIGNING);
      const signedUploadXdr = await signWithFreighter(uploadXdr, NETWORKS[network]);

      // Step 4: Submit upload transaction
      setStatus(STATUS.DEPLOYING);
      const submitUploadRes = await fetch("/api/soroban/submit-tx", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${authToken}` },
        body: JSON.stringify({
          signed_xdr: signedUploadXdr,
        }),
      });

      if (!submitUploadRes.ok) {
        const err = await submitUploadRes.json();
        throw new Error(err.error || "WASM upload failed");
      }

      const { wasm_hash } = await submitUploadRes.json();

      // Step 5: Create contract instance
      setStatus(STATUS.BUILDING);
      const createRes = await fetch("/api/soroban/prepare-create", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${authToken}` },
        body: JSON.stringify({
          session_id: sessionId,
          wasm_hash: wasm_hash,
          public_key: publicKey,
        }),
      });

      if (!createRes.ok) {
        const err = await createRes.json();
        throw new Error(err.error || "Failed to prepare create transaction");
      }

      const { unsigned_xdr: createXdr } = await createRes.json();

      // Step 6: Sign create transaction
      setStatus(STATUS.SIGNING);
      const signedCreateXdr = await signWithFreighter(createXdr, NETWORKS[network]);

      // Step 7: Submit create transaction
      setStatus(STATUS.DEPLOYING);
      const submitCreateRes = await fetch("/api/soroban/submit-tx", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": `Bearer ${authToken}` },
        body: JSON.stringify({
          signed_xdr: signedCreateXdr,
        }),
      });

      if (!submitCreateRes.ok) {
        const err = await submitCreateRes.json();
        throw new Error(err.error || "Contract creation failed");
      }

      const { contract_id } = await submitCreateRes.json();
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
