import { useCallback, useEffect, useRef, useState } from "react";

import {
  getPersistableProject,
  serializePersistableProject,
} from "../../core/PageBuilder.editorState";
import {
  createBuilderRecoveryEnvelope,
} from "../../core/PageBuilder.recovery";

const BUILDER_DRAFT_SYNC_CHANNEL = "madar-builder-draft-sync";
const createSourceId = () =>
  typeof crypto !== "undefined" && crypto.randomUUID
    ? `builder-tab-${crypto.randomUUID()}`
    : `builder-tab-${Date.now()}-${Math.random().toString(16).slice(2)}`;

export function isNewerExternalDraftMessage(candidate, {
  currentBackendRevision = 0,
  currentProjectId = "",
  currentTenantId = "",
  lastPersistedAt = 0,
  sourceId = "",
} = {}) {
  if (!candidate?.serializedProject || candidate.sourceId === sourceId) return false;
  if (candidate.projectId && currentProjectId && candidate.projectId !== currentProjectId) return false;
  if (candidate.tenantId && currentTenantId && candidate.tenantId !== currentTenantId) return false;
  if (
    Number.isInteger(Number(candidate.baseDraftRevision)) &&
    Number(candidate.baseDraftRevision) < Number(currentBackendRevision || 0)
  ) return false;
  if (candidate.timestamp && candidate.timestamp <= lastPersistedAt) return false;
  return true;
}

export default function useDebouncedProjectStorage({
  backupInterval = 120000,
  delay = 7000,
  disabled = false,
  enableBrowserPersistence = true,
  project,
  recoveryContext = null,
  storageKey,
}) {
  const timerRef = useRef(null);
  const latestProjectRef = useRef(project);
  const lastSerializedRef = useRef("");
  const lastObservedSerializedRef = useRef("");
  const lastPersistedAtRef = useRef(0);
  const dirtyRef = useRef(false);
  const currentRevisionRef = useRef(0);
  const lastSuccessfullySavedRevisionRef = useRef(0);
  const [sourceId] = useState(createSourceId);
  const channelRef = useRef(null);

  useEffect(() => {
    if (disabled || !storageKey) return;
    // A recovery envelope is pending browser work, not the cloud baseline.
    // Backend hydration calls acceptExternalRevision with the authoritative schema.
    if (recoveryContext) return;
    try {
      const stored = localStorage.getItem(storageKey) || "";
      lastSerializedRef.current = stored
        ? serializePersistableProject(JSON.parse(stored))
        : "";
    } catch {
      lastSerializedRef.current = "";
    }
  }, [disabled, recoveryContext, storageKey]);

  useEffect(() => {
    if (typeof BroadcastChannel === "undefined") return undefined;
    channelRef.current = new BroadcastChannel(BUILDER_DRAFT_SYNC_CHANNEL);
    return () => {
      channelRef.current?.close();
      channelRef.current = null;
    };
  }, []);

  useEffect(() => {
    latestProjectRef.current = project;
    if (disabled || !project) return;
    try {
      const serializedProject = serializePersistableProject(project);
      if (serializedProject !== lastObservedSerializedRef.current) {
        currentRevisionRef.current += 1;
        lastObservedSerializedRef.current = serializedProject;
      }
      dirtyRef.current = serializedProject !== lastSerializedRef.current;
    } catch {
      dirtyRef.current = true;
    }
  }, [disabled, project]);

  const clearPersistTimer = useCallback(() => {
    if (timerRef.current === null) return;
    window.clearTimeout(timerRef.current);
    timerRef.current = null;
  }, []);

  const persistNow = useCallback(
    (nextProject = latestProjectRef.current) => {
      if (disabled || !enableBrowserPersistence || !storageKey || !nextProject) return false;

      try {
        const persistableProject = getPersistableProject(nextProject);
        const serializedProject = serializePersistableProject(persistableProject);
        if (serializedProject !== lastObservedSerializedRef.current) {
          currentRevisionRef.current += 1;
          lastObservedSerializedRef.current = serializedProject;
        }
        if (serializedProject === lastSerializedRef.current) {
          dirtyRef.current = false;
          return false;
        }

        const storedValue = recoveryContext
          ? JSON.stringify(createBuilderRecoveryEnvelope({
              ...recoveryContext,
              schema: persistableProject,
            }))
          : serializedProject;
        localStorage.setItem(storageKey, storedValue);

        const timestamp = Date.now();
        const savedRevision = Math.max(1, currentRevisionRef.current);
        channelRef.current?.postMessage({
          baseDraftRevision: Number(recoveryContext?.baseDraftRevision) || 0,
          sourceId,
          revision: savedRevision,
          storageKey,
          projectId: recoveryContext?.projectId || persistableProject.id || "",
          tenantId: String(recoveryContext?.tenantId || ""),
          timestamp,
          serializedProject,
        });
        lastSerializedRef.current = serializedProject;
        lastObservedSerializedRef.current = serializedProject;
        lastPersistedAtRef.current = timestamp;
        lastSuccessfullySavedRevisionRef.current = savedRevision;
        dirtyRef.current = false;
        return true;
      } catch {
        dirtyRef.current = true;
        if (import.meta.env.DEV) console.warn("Could not persist builder draft.");
        return false;
      }
    },
    [disabled, enableBrowserPersistence, recoveryContext, sourceId, storageKey]
  );

  const acknowledgeCloudSave = useCallback((savedProject, baseDraftRevision = null) => {
    if (!savedProject) return false;
    const acknowledged = serializePersistableProject(savedProject);
    lastSerializedRef.current = acknowledged;
    lastObservedSerializedRef.current = acknowledged;
    try {
      if (storageKey) {
        localStorage.removeItem(storageKey);
        localStorage.removeItem(`${storageKey}:backup`);
      }
    } catch {
      // Cloud acknowledgement remains authoritative even if recovery cleanup fails.
    }
    const latest = latestProjectRef.current
      ? serializePersistableProject(latestProjectRef.current)
      : acknowledged;
    dirtyRef.current = latest !== acknowledged;
    if (
      enableBrowserPersistence &&
      dirtyRef.current &&
      storageKey &&
      recoveryContext &&
      latestProjectRef.current
    ) {
      try {
        localStorage.setItem(
          storageKey,
          JSON.stringify(createBuilderRecoveryEnvelope({
            ...recoveryContext,
            ...(baseDraftRevision === null
              ? {}
              : { baseDraftRevision }),
            schema: latestProjectRef.current,
          }))
        );
      } catch {
        // The visible cloud state remains dirty even if recovery storage is unavailable.
      }
    }
    return dirtyRef.current;
  }, [enableBrowserPersistence, recoveryContext, storageKey]);

  const adoptCloudRevision = useCallback((serializedProject, timestamp = Date.now(), revision = 0) => {
    if (!serializedProject) return;
    clearPersistTimer();
    lastSerializedRef.current = serializedProject;
    lastObservedSerializedRef.current = serializedProject;
    lastPersistedAtRef.current = Math.max(lastPersistedAtRef.current, Number(timestamp) || 0);
    currentRevisionRef.current = Math.max(currentRevisionRef.current, Number(revision) || 0);
    lastSuccessfullySavedRevisionRef.current = currentRevisionRef.current;
    dirtyRef.current = false;
  }, [clearPersistTimer]);

  const getLastPersistedAt = useCallback(() => lastPersistedAtRef.current, []);
  const getRevisionState = useCallback(() => ({
    currentRevision: currentRevisionRef.current,
    lastSuccessfullySavedRevision: lastSuccessfullySavedRevisionRef.current,
  }), []);
  const hasUnsavedChanges = useCallback(() => dirtyRef.current, []);

  useEffect(() => {
    if (disabled || !enableBrowserPersistence || !storageKey || !project) {
      clearPersistTimer();
      return undefined;
    }

    clearPersistTimer();
    if (!dirtyRef.current) return undefined;
    timerRef.current = window.setTimeout(() => persistNow(project), delay);
    return clearPersistTimer;
  }, [clearPersistTimer, delay, disabled, enableBrowserPersistence, persistNow, project, storageKey]);

  useEffect(() => {
    if (disabled || !enableBrowserPersistence || !backupInterval) return undefined;
    const intervalId = window.setInterval(() => {
      if (dirtyRef.current) persistNow(latestProjectRef.current);
    }, backupInterval);
    return () => window.clearInterval(intervalId);
  }, [backupInterval, disabled, enableBrowserPersistence, persistNow]);

  useEffect(() => {
    if (disabled || !enableBrowserPersistence) return undefined;
    const persistLatest = () => persistNow(latestProjectRef.current);
    const handleVisibility = () => {
      if (document.visibilityState === "hidden") persistLatest();
    };
    window.addEventListener("blur", persistLatest);
    window.addEventListener("pagehide", persistLatest);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.removeEventListener("blur", persistLatest);
      window.removeEventListener("pagehide", persistLatest);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [disabled, enableBrowserPersistence, persistNow]);

  useEffect(() => clearPersistTimer, [clearPersistTimer]);

  return {
    acknowledgeCloudSave,
    acceptExternalRevision: adoptCloudRevision,
    adoptCloudRevision,
    getLastPersistedAt,
    getRevisionState,
    hasUnsavedChanges,
    persistNow,
    sourceId,
  };
}
