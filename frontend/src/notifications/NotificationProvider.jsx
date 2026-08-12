import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../services/notificationsApi";
import { createToastCoordinator } from "./toastCoordinator";
import { createNotificationPollingLeader } from "./pollingLeader";
import { NotificationContext } from "./NotificationContext";
import {
  chronologicalNotifications,
  getNotificationIdentity,
  normalizeNotification,
  notificationKey,
  notificationProviderConstants,
  readSessionDedup,
  rememberSessionDedup,
} from "./notificationState";

const {
  FETCH_LIMIT,
  MAX_KNOWN_IDS,
  MAX_TOAST_QUEUE,
  POLL_INTERVAL_MS,
} = notificationProviderConstants;

export function NotificationProvider({
  children,
  user,
  pollIntervalMs = POLL_INTERVAL_MS,
  claimToast,
}) {
  const identity = getNotificationIdentity(user);
  const activeIdentityRef = useRef(identity);
  activeIdentityRef.current = identity;
  const [state, setState] = useState({
    identity: "",
    notifications: [],
    unreadCount: 0,
    loading: false,
    error: null,
  });
  const [toastQueue, setToastQueue] = useState([]);
  const [isPollingLeader, setIsPollingLeader] = useState(false);
  const baselineRef = useRef({ identity: "", established: false, ids: new Set() });
  const inFlightRef = useRef(null);
  const coordinatorRef = useRef(null);
  const pollingLeaderRef = useRef(null);

  useEffect(() => {
    if (claimToast) return undefined;
    const coordinator = createToastCoordinator();
    coordinatorRef.current = coordinator;
    return () => {
      coordinator.close();
      coordinatorRef.current = null;
    };
  }, [claimToast]);

  const enqueueNewToasts = useCallback(async (items, requestIdentity) => {
    const sessionDedup = readSessionDedup(requestIdentity);
    const candidates = chronologicalNotifications(items).filter((item) => (
      item.id
      && !sessionDedup.has(notificationKey(requestIdentity, item.id))
      && !(item.eventId && sessionDedup.has(notificationKey(requestIdentity, `event:${item.eventId}`)))
    ));
    const claim = claimToast || coordinatorRef.current?.claim;
    const results = await Promise.all(candidates.map(async (item) => {
      const key = notificationKey(requestIdentity, item.id);
      const won = claim ? await claim(key) : true;
      return won ? { item, key } : null;
    }));
    if (activeIdentityRef.current !== requestIdentity) return;
    const winners = results.filter(Boolean);
    if (!winners.length) return;
    winners.forEach(({ key }) => rememberSessionDedup(requestIdentity, key));
    setToastQueue((current) => {
      const currentKeys = new Set(current.map((entry) => entry.key));
      const additions = winners
        .filter(({ key }) => !currentKeys.has(key))
        .map(({ item, key }) => ({ ...item, key, identity: requestIdentity }));
      return [...current, ...additions].slice(-MAX_TOAST_QUEUE);
    });
  }, [claimToast]);

  const refreshNotifications = useCallback(async () => {
    const requestIdentity = identity;
    if (!requestIdentity) return null;
    if (inFlightRef.current?.identity === requestIdentity) {
      return inFlightRef.current.promise;
    }

    const controller = new AbortController();
    const promise = (async () => {
      setState((current) => current.identity === requestIdentity
        ? { ...current, loading: current.notifications.length === 0, error: null }
        : {
            identity: requestIdentity,
            notifications: [],
            unreadCount: 0,
            loading: true,
            error: null,
          });
      try {
        const data = await fetchNotifications({ limit: FETCH_LIMIT, signal: controller.signal });
        if (activeIdentityRef.current !== requestIdentity) return null;
        const notifications = (data.notifications || data.items || [])
          .map(normalizeNotification)
          .filter((item) => item.id);
        const baseline = baselineRef.current;
        const isInitialSuccess = baseline.identity !== requestIdentity || !baseline.established;
        const knownIds = isInitialSuccess ? new Set() : baseline.ids;
        const newlyObserved = isInitialSuccess
          ? []
          : notifications.filter((item) => !knownIds.has(item.id));
        const nextIds = new Set([
          ...notifications.map((item) => item.id),
          ...knownIds,
        ].slice(0, MAX_KNOWN_IDS));
        baselineRef.current = {
          identity: requestIdentity,
          established: true,
          ids: nextIds,
        };
        setState({
          identity: requestIdentity,
          notifications,
          unreadCount: Number(data.unread_count || 0),
          loading: false,
          error: null,
        });
        if (newlyObserved.length) {
          await enqueueNewToasts(newlyObserved, requestIdentity);
        }
        return data;
      } catch (error) {
        if (error?.name === "AbortError" || activeIdentityRef.current !== requestIdentity) {
          return null;
        }
        setState((current) => current.identity === requestIdentity
          ? { ...current, loading: false, error }
          : {
              identity: requestIdentity,
              notifications: [],
              unreadCount: 0,
              loading: false,
              error,
            });
        return null;
      } finally {
        if (inFlightRef.current?.controller === controller) inFlightRef.current = null;
      }
    })();
    inFlightRef.current = { controller, identity: requestIdentity, promise };
    return promise;
  }, [enqueueNewToasts, identity]);

  useEffect(() => {
    if (!identity) {
      setIsPollingLeader(false);
      return undefined;
    }
    const leader = createNotificationPollingLeader({
      identity,
      onLeadershipChange: setIsPollingLeader,
      onRefreshRequested: refreshNotifications,
    });
    pollingLeaderRef.current = leader;
    if (!leader.supported) setIsPollingLeader(true);
    leader.start();
    return () => {
      leader.stop();
      if (pollingLeaderRef.current === leader) pollingLeaderRef.current = null;
    };
  }, [identity, refreshNotifications]);

  useEffect(() => {
    inFlightRef.current?.controller?.abort();
    baselineRef.current = { identity, established: false, ids: new Set() };
    const resetTimer = window.setTimeout(() => {
      setToastQueue((current) => current.filter((item) => item.identity === identity));
      if (!identity) {
        setState({
          identity: "",
          notifications: [],
          unreadCount: 0,
          loading: false,
          error: null,
        });
      }
    }, 0);
    if (!identity) return () => window.clearTimeout(resetTimer);

    if (isPollingLeader) refreshNotifications();
    const poll = () => {
      if (document.visibilityState === "hidden") return;
      const leader = pollingLeaderRef.current;
      if (leader?.supported) leader.requestRefresh();
      else refreshNotifications();
    };
    const interval = isPollingLeader && pollIntervalMs > 0
      ? window.setInterval(poll, pollIntervalMs)
      : null;
    window.addEventListener("focus", poll);
    document.addEventListener("visibilitychange", poll);
    return () => {
      window.clearTimeout(resetTimer);
      inFlightRef.current?.controller?.abort();
      if (interval) window.clearInterval(interval);
      window.removeEventListener("focus", poll);
      document.removeEventListener("visibilitychange", poll);
    };
  }, [identity, isPollingLeader, pollIntervalMs, refreshNotifications]);

  useEffect(() => {
    const rememberPushPresentation = (event) => {
      if (event.data?.type !== "MADAR_PUSH_PRESENTED" || !identity) return;
      const eventId = String(event.data.event_id || "");
      if (/^[A-Za-z0-9-]{1,100}$/.test(eventId)) {
        rememberSessionDedup(identity, notificationKey(identity, `event:${eventId}`));
      }
    };
    navigator.serviceWorker?.addEventListener?.("message", rememberPushPresentation);
    return () => navigator.serviceWorker?.removeEventListener?.("message", rememberPushPresentation);
  }, [identity]);

  const markRead = useCallback(async (notificationId) => {
    const requestIdentity = identity;
    if (!requestIdentity || !notificationId) return false;
    try {
      await markNotificationRead(notificationId);
      if (activeIdentityRef.current !== requestIdentity) return false;
      setState((current) => {
        if (current.identity !== requestIdentity) return current;
        const wasUnread = current.notifications.some(
          (item) => item.id === notificationId && item.unread
        );
        return {
          ...current,
          notifications: current.notifications.map((item) => item.id === notificationId
            ? { ...item, unread: false, readAt: item.readAt || new Date().toISOString() }
            : item),
          unreadCount: wasUnread ? Math.max(0, current.unreadCount - 1) : current.unreadCount,
        };
      });
      return true;
    } catch {
      return false;
    }
  }, [identity]);

  const markAllRead = useCallback(async () => {
    const requestIdentity = identity;
    if (!requestIdentity) return false;
    try {
      await markAllNotificationsRead();
      if (activeIdentityRef.current !== requestIdentity) return false;
      setState((current) => current.identity === requestIdentity
        ? {
            ...current,
            notifications: current.notifications.map((item) => ({
              ...item,
              unread: false,
              readAt: item.readAt || new Date().toISOString(),
            })),
            unreadCount: 0,
          }
        : current);
      return true;
    } catch {
      return false;
    }
  }, [identity]);

  const dismissToast = useCallback((key) => {
    setToastQueue((current) => current.filter((item) => item.key !== key));
  }, []);

  const identityMatches = Boolean(identity && state.identity === identity);
  const value = useMemo(() => ({
    dismissToast,
    error: identityMatches ? state.error : null,
    identity,
    loading: Boolean(identity) && (identityMatches ? state.loading : true),
    markAllRead,
    markRead,
    notifications: identityMatches ? state.notifications : [],
    refreshNotifications,
    toastQueue: toastQueue.filter((item) => item.identity === identity),
    tenantId: String(user?.tenant_id || ""),
    unreadCount: identityMatches ? state.unreadCount : 0,
  }), [
    dismissToast,
    identity,
    identityMatches,
    markAllRead,
    markRead,
    refreshNotifications,
    state,
    toastQueue,
    user?.tenant_id,
  ]);

  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>;
}
