import { useEffect, useRef, useState } from "react";
import { apiFetch, getApiUrl } from "../utils/apiClient";

const STORAGE_PREFIX = "madar:weekly-screen-time:v1:";
const TICK_INTERVAL_MS = 1000;
const MAX_TICK_SECONDS = 2;
const PERSIST_INTERVAL_MS = 10000;

export function getWeeklyScreenTimeWeekKey(value = new Date()) {
  const date = new Date(value);
  date.setHours(0, 0, 0, 0);
  const daysSinceMonday = (date.getDay() + 6) % 7;
  date.setDate(date.getDate() - daysSinceMonday);
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

export function formatWeeklyScreenTime(totalSeconds) {
  const seconds = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const totalMinutes = Math.floor(seconds / 60);
  if (totalMinutes < 60) return totalMinutes + " min";

  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return minutes ? hours + "h " + minutes + "m" : hours + "h";
}

function readStoredTime(storageKey, weekKey) {
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey) || "null");
    if (stored?.week === weekKey) return Math.max(0, Number(stored.seconds) || 0);
  } catch {
    // A malformed or unavailable local entry should not interrupt the workspace.
  }
  return 0;
}

function writeStoredTime(storageKey, weekKey, seconds) {
  try {
    localStorage.setItem(
      storageKey,
      JSON.stringify({ week: weekKey, seconds: Math.max(0, seconds) })
    );
  } catch {
    // Screen-time tracking remains best effort when storage is unavailable.
  }
}

function isAppActivelyViewed() {
  if (document.visibilityState !== "visible") return false;
  return typeof document.hasFocus !== "function" || document.hasFocus();
}

export default function useWeeklyScreenTime(
  user,
  { endpoint = "/screen-time/heartbeat", scope = "workspace" } = {}
) {
  const userKey = String(user?.id || user?.auth_id || user?.email || "").trim();
  const storageKey = userKey ? STORAGE_PREFIX + scope + ":" + userKey : "";
  const weekKeyRef = useRef("");
  const secondsRef = useRef(0);
  const pendingHeartbeatRef = useRef(0);
  const heartbeatInFlightRef = useRef(false);
  const lastTickRef = useRef(0);
  const lastPersistRef = useRef(0);
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    if (!storageKey) {
      secondsRef.current = 0;
      pendingHeartbeatRef.current = 0;
      const resetId = window.setTimeout(() => setSeconds(0), 0);
      return () => window.clearTimeout(resetId);
    }

    weekKeyRef.current = getWeeklyScreenTimeWeekKey();
    secondsRef.current = readStoredTime(storageKey, weekKeyRef.current);
    pendingHeartbeatRef.current = 0;
    lastTickRef.current = Date.now();
    lastPersistRef.current = Date.now();
    const initialUpdateId = window.setTimeout(
      () => setSeconds(Math.floor(secondsRef.current)),
      0
    );

    const flushHeartbeat = () => {
      if (heartbeatInFlightRef.current) return;
      const activeSeconds = Math.min(60, Math.floor(pendingHeartbeatRef.current));
      if (activeSeconds < 1) return;

      pendingHeartbeatRef.current -= activeSeconds;
      heartbeatInFlightRef.current = true;
      apiFetch(getApiUrl(endpoint), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ active_seconds: activeSeconds }),
      })
        .then((response) => {
          if (!response.ok) pendingHeartbeatRef.current += activeSeconds;
        })
        .catch(() => {
          pendingHeartbeatRef.current += activeSeconds;
        })
        .finally(() => {
          heartbeatInFlightRef.current = false;
        });
    };

    const persist = () => {
      writeStoredTime(storageKey, weekKeyRef.current, secondsRef.current);
      flushHeartbeat();
      lastPersistRef.current = Date.now();
    };

    const tick = () => {
      const now = Date.now();
      const currentWeek = getWeeklyScreenTimeWeekKey(now);

      if (currentWeek !== weekKeyRef.current) {
        weekKeyRef.current = currentWeek;
        secondsRef.current = 0;
        pendingHeartbeatRef.current = 0;
        setSeconds(0);
      }

      const elapsedSeconds = Math.min(
        MAX_TICK_SECONDS,
        Math.max(0, (now - lastTickRef.current) / 1000)
      );
      lastTickRef.current = now;

      if (isAppActivelyViewed()) {
        secondsRef.current += elapsedSeconds;
        pendingHeartbeatRef.current += elapsedSeconds;
        setSeconds(Math.floor(secondsRef.current));
      }

      if (now - lastPersistRef.current >= PERSIST_INTERVAL_MS) persist();
    };

    const resetTickBaseline = () => {
      lastTickRef.current = Date.now();
      if (document.visibilityState !== "visible") persist();
    };

    const syncAcrossTabs = (event) => {
      if (event.key !== storageKey) return;
      const storedSeconds = readStoredTime(storageKey, weekKeyRef.current);
      if (storedSeconds > secondsRef.current) {
        secondsRef.current = storedSeconds;
        setSeconds(Math.floor(storedSeconds));
      }
    };

    const intervalId = window.setInterval(tick, TICK_INTERVAL_MS);
    document.addEventListener("visibilitychange", resetTickBaseline);
    window.addEventListener("focus", resetTickBaseline);
    window.addEventListener("blur", resetTickBaseline);
    window.addEventListener("pagehide", persist);
    window.addEventListener("storage", syncAcrossTabs);

    return () => {
      window.clearTimeout(initialUpdateId);
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", resetTickBaseline);
      window.removeEventListener("focus", resetTickBaseline);
      window.removeEventListener("blur", resetTickBaseline);
      window.removeEventListener("pagehide", persist);
      window.removeEventListener("storage", syncAcrossTabs);
      persist();
    };
  }, [endpoint, storageKey]);

  return seconds;
}