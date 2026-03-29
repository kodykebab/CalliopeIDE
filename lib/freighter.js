import {
  isConnected,
  getPublicKey,
  signTransaction,
} from "@stellar/freighter-api";

export async function checkFreighter() {
  const connected = await isConnected();
  if (!connected) {
    throw new Error(
      "Freighter wallet not found. Please install the " +
      "Freighter browser extension."
    );
  }
  return true;
}

export async function getWalletPublicKey() {
  await checkFreighter();
  const publicKey = await getPublicKey();
  if (!publicKey) {
    throw new Error(
      "No public key returned. Please unlock Freighter " +
      "and grant access to this site."
    );
  }
  return publicKey;
}

export async function signWithFreighter(xdr, networkPassphrase) {
  await checkFreighter();
  const result = await signTransaction(xdr, {
    networkPassphrase,
  });
  if (result.error) {
    throw new Error("Freighter signing failed: " + result.error);
  }
  return result.signedTxXdr;
}

export const NETWORKS = {
  testnet: "Test SDF Network ; September 2015",
  mainnet: "Public Global Stellar Network ; September 2015",
};
