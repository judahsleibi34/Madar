import { useCallback, useEffect, useRef, useState } from "react";

const BUILDER_DRAFT_SYNC_CHANNEL = "madar-builder-draft-sync";
const createSourceId = () =>
  typeof crypto !== "undefined" && crypto.randomUUID
    ? `builder-tab-${crypto.randomUUID()}`
    : `builder-tab-${Date.now()}-${Math.random().toString(16).slice(2)}`;

export function isNewerExternalDraftMessage(candidate, {
  currentProjectId = "",
  lastPersistedAt = 0,
  previousRevision = 0,
  sourceId = "",
} = {}) {
  if (!candidate?.serializedProject || candidate.sourceId === sourceId) return false;
  if (candidate.projectId && currentProjectId && candidate.projectId !== currentProjectId) return false;
  if (candidate.revision && candidate.revision <= previousRevision) return false;
  if (candidate.timestamp && candidate.timestamp <= lastPersistedAt) return false;
  return true;
}

export default function useDebouncedProjectStorage({
  backupInterval = 120000,
  delay = 7000,
  disabled = false,
  project,
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
    try {
      lastSerializedRef.current = localStorage.getItem(storageKey) || "";
    } catch {
      lastSerializedRef.current = "";
    }
  }, [disabled, storageKey]);

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
      const serializedProject = JSON.stringify(project);
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
      if (disabled || !storageKey || !nextProject) return false;

      try {
        const serializedProject = JSON.stringify(nextProject);
        if (serializedProject !== lastObservedSerializedRef.current) {
          currentRevisionRef.current += 1;
          lastObservedSerializedRef.current = serializedProject;
        }
        if (serializedProject === lastSerializedRef.current) {
          dirtyRef.current = false;
          return false;
        }

        const previousDraft = localStorage.getItem(storageKey);
        if (previousDraft && previousDraft !== serializedProject) {
          localStorage.setItem(`${storageKey}:backup`, previousDraft);
        }
        localStorage.setItem(storageKey, serializedProject);

        const timestamp = Date.now();
        const savedRevision = Math.max(1, currentRevisionRef.current);
        channelRef.current?.postMessage({
          sourceId,
          revision: savedRevision,
          storageKey,
          projectId: nextProject.id || "",
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
    [disabled, sourceId, storageKey]
  );

  const acceptExternalRevision = useCallback((serializedProject, timestamp = Date.now(), revision = 0) => {
    if (!serializedProject) return;
    lastSerializedRef.current = serializedProject;
    lastObservedSerializedRef.current = serializedProject;
    lastPersistedAtRef.current = Math.max(lastPersistedAtRef.current, Number(timestamp) || 0);
    currentRevisionRef.current = Math.max(currentRevisionRef.current, Number(revision) || 0);
    lastSuccessfullySavedRevisionRef.current = currentRevisionRef.current;
    dirtyRef.current = false;
  }, []);

  const getLastPersistedAt = useCallback(() => lastPersistedAtRef.current, []);
  const getRevisionState = useCallback(() => ({
    currentRevision: currentRevisionRef.current,
    lastSuccessfullySavedRevision: lastSuccessfullySavedRevisionRef.current,
  }), []);
  const hasUnsavedChanges = useCallback(() => dirtyRef.current, []);

  useEffect(() => {
    if (disabled || !storageKey || !project) {
      clearPersistTimer();
      return undefined;
    }

    clearPersistTimer();
    if (!dirtyRef.current) return undefined;
    timerRef.current = window.setTimeout(() => persistNow(project), delay);
    return clearPersistTimer;
  }, [clearPersistTimer, delay, disabled, persistNow, project, storageKey]);

  useEffect(() => {
    if (disabled || !backupInterval) return undefined;
    const intervalId = window.setInterval(() => {
      if (dirtyRef.current) persistNow(latestProjectRef.current);
    }, backupInterval);
    return () => window.clearInterval(intervalId);
  }, [backupInterval, disabled, persistNow]);

  useEffect(() => {
    if (disabled) return undefined;
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
  }, [disabled, persistNow]);

  useEffect(() => clearPersistTimer, [clearPersistTimer]);

  return {
    acceptExternalRevision,
    getLastPersistedAt,
    getRevisionState,
    hasUnsavedChanges,
    persistNow,
    sourceId,
  };
}
