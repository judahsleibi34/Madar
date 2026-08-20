const CHANNEL_NAME = "madar-notifications-v1";
const SHARED_CLAIMS_KEY = "madar-notification-toast-claims-v1";
const CLAIM_TTL_MS = 24 * 60 * 60 * 1000;
const MAX_SHARED_CLAIMS = 300;

const randomId = () => globalThis.crypto?.randomUUID?.()
  || `${Date.now()}-${Math.random().toString(16).slice(2)}`;

const hashKey = (value) => {
  let hash = 2166136261;
  for (const character of String(value)) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
};

function readClaims(storage, now = Date.now()) {
  try {
    const parsed = JSON.parse(storage?.getItem(SHARED_CLAIMS_KEY) || "[]");
    return (Array.isArray(parsed) ? parsed : [])
      .filter((item) => item?.key && now - Number(item.at || 0) < CLAIM_TTL_MS)
      .slice(-MAX_SHARED_CLAIMS);
  } catch {
    return [];
  }
}

function writeClaim(storage, key, claimId, now = Date.now()) {
  if (!storage) return;
  try {
    const claims = readClaims(storage, now).filter((item) => item.key !== key);
    claims.push({ key, claimId, at: now });
    storage.setItem(SHARED_CLAIMS_KEY, JSON.stringify(claims.slice(-MAX_SHARED_CLAIMS)));
  } catch {
    // Storage can be unavailable in privacy modes. BroadcastChannel can still
    // coordinate tabs during the current page lifetime.
  }
}

export function createToastCoordinator({
  windowLike = globalThis.window,
  arbitrationMs = 50,
} = {}) {
  const tabId = randomId();
  const contenders = new Map();
  const claimed = new Set();
  const storage = windowLike?.localStorage;
  let channel = null;

  try {
    channel = typeof windowLike?.BroadcastChannel === "function"
      ? new windowLike.BroadcastChannel(CHANNEL_NAME)
      : null;
  } catch {
    channel = null;
  }

  const rememberContender = (key, candidate) => {
    const candidates = contenders.get(key) || new Set();
    candidates.add(candidate);
    contenders.set(key, candidates);
  };

  if (channel) {
    channel.onmessage = (event) => {
      const message = event?.data;
      if (!message?.key) return;
      if (message.type === "candidate") rememberContender(message.key, message.claimId);
      if (message.type === "claimed") claimed.add(message.key);
    };
  }

  const alreadyClaimed = (key) => (
    claimed.has(key) || readClaims(storage).some((item) => item.key === key)
  );

  const persistWinner = (key, claimId) => {
    claimed.add(key);
    writeClaim(storage, key, claimId);
    channel?.postMessage({ type: "claimed", key, claimId, tabId });
  };

  const claimWithStorage = async (key, claimId) => {
    if (alreadyClaimed(key)) return false;
    writeClaim(storage, key, claimId);
    const winner = readClaims(storage).find((item) => item.key === key);
    if (!winner) {
      // Storage can be blocked or non-persistent. In that case notification
      // delivery must keep working even though cross-tab exclusion is best effort.
      persistWinner(key, claimId);
      return true;
    }
    if (winner?.claimId !== claimId) return false;
    persistWinner(key, claimId);
    return true;
  };

  const claim = async (key) => {
    if (!key || alreadyClaimed(key)) return false;
    const claimId = `${tabId}:${randomId()}`;
    const lockName = `madar-toast-${hashKey(key)}`;

    if (windowLike?.navigator?.locks?.request) {
      return windowLike.navigator.locks.request(lockName, async () => (
        claimWithStorage(key, claimId)
      ));
    }

    if (!channel) return claimWithStorage(key, claimId);

    rememberContender(key, claimId);
    channel.postMessage({ type: "candidate", key, claimId, tabId });
    await new Promise((resolve) => windowLike.setTimeout(resolve, arbitrationMs));
    if (alreadyClaimed(key)) return false;
    const winner = [...(contenders.get(key) || [])].sort()[0];
    if (winner !== claimId) return false;
    persistWinner(key, claimId);
    contenders.delete(key);
    return true;
  };

  return {
    claim,
    close() {
      channel?.close?.();
      contenders.clear();
      claimed.clear();
    },
    supported: Boolean(channel || windowLike?.navigator?.locks?.request),
  };
}

export const toastCoordinatorConstants = {
  CHANNEL_NAME,
  CLAIM_TTL_MS,
  MAX_SHARED_CLAIMS,
  SHARED_CLAIMS_KEY,
};
