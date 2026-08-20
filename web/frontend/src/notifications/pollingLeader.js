const CHANNEL_NAME = "madar-notification-poll-v1";
const HEARTBEAT_MS = 5_000;
const STALE_AFTER_MS = 15_000;

const randomId = () => globalThis.crypto?.randomUUID?.()
  || `${Date.now()}-${Math.random().toString(16).slice(2)}`;

export function createNotificationPollingLeader({
  identity,
  windowLike = globalThis.window,
  documentLike = globalThis.document,
  onLeadershipChange = () => {},
  onRefreshRequested = () => {},
} = {}) {
  if (!identity || !windowLike?.localStorage || typeof windowLike.BroadcastChannel !== "function") {
    return { supported: false, requestRefresh() {}, start() {}, stop() {} };
  }
  const tabId = randomId();
  const storageKey = `madar-notification-poll-leader:v1:${identity}`;
  let channel;
  let interval;
  let leader = false;

  const read = () => {
    try { return JSON.parse(windowLike.localStorage.getItem(storageKey) || "null"); } catch { return null; }
  };
  const write = () => {
    try { windowLike.localStorage.setItem(storageKey, JSON.stringify({ tabId, at: Date.now() })); } catch { /* fall back below */ }
  };
  const setLeader = (next) => {
    if (leader === next) return;
    leader = next;
    onLeadershipChange(next);
  };
  const relinquish = () => {
    if (leader && read()?.tabId === tabId) {
      try { windowLike.localStorage.removeItem(storageKey); } catch { /* ignored */ }
    }
    setLeader(false);
  };
  const elect = () => {
    // A hidden tab must not hold the polling lease while a visible sibling can
    // keep the inbox current. Its heartbeat is intentionally removed so a
    // visible tab can take over at the next election.
    if (documentLike?.visibilityState === "hidden") {
      relinquish();
      return;
    }
    const current = read();
    const stale = !current || Date.now() - Number(current.at || 0) > STALE_AFTER_MS;
    if (stale || current.tabId === tabId) write();
    const winner = read();
    setLeader(Boolean(winner?.tabId === tabId));
  };
  const start = () => {
    try {
      channel = new windowLike.BroadcastChannel(CHANNEL_NAME);
      channel.onmessage = (event) => {
        const message = event.data;
        if (message?.identity !== identity) return;
        if (message.type === "refresh" && leader) onRefreshRequested();
      };
    } catch {
      channel = null;
      return;
    }
    elect();
    interval = windowLike.setInterval(elect, HEARTBEAT_MS);
    documentLike?.addEventListener?.("visibilitychange", elect);
  };
  const requestRefresh = () => {
    if (leader) onRefreshRequested();
    else channel?.postMessage({ type: "refresh", identity });
  };
  const stop = () => {
    if (interval) windowLike.clearInterval(interval);
    interval = null;
    documentLike?.removeEventListener?.("visibilitychange", elect);
    relinquish();
    channel?.close?.();
    channel = null;
  };
  return { supported: true, requestRefresh, start, stop };
}

export const pollingLeaderConstants = { CHANNEL_NAME, HEARTBEAT_MS, STALE_AFTER_MS };
