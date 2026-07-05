import { useCallback, useEffect, useRef } from "react";

const BUILDER_DRAFT_SYNC_CHANNEL = "madar-builder-draft-sync";

export default function useDebouncedProjectStorage({
  delay = 600,
  disabled = false,
  project,
  storageKey,
}) {
  const timerRef = useRef(null);
  const latestProjectRef = useRef(project);
  const lastSerializedRef = useRef("");
  const channelRef = useRef(null);

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
  }, [project]);

  const clearPersistTimer = useCallback(() => {
    if (!timerRef.current) return;
    window.clearTimeout(timerRef.current);
    timerRef.current = null;
  }, []);

  const persistNow = useCallback(
    (nextProject = latestProjectRef.current) => {
      if (disabled || !storageKey || !nextProject) return;

      try {
        const serializedProject = JSON.stringify(nextProject);

        if (serializedProject === lastSerializedRef.current) return;

        localStorage.setItem(storageKey, serializedProject);
        channelRef.current?.postMessage({
          storageKey,
          serializedProject,
        });
        lastSerializedRef.current = serializedProject;
      } catch {
        if (import.meta.env.DEV) {
          console.warn("Could not persist builder draft.");
        }
      }
    },
    [disabled, storageKey]
  );

  useEffect(() => {
    if (disabled || !storageKey || !project) {
      clearPersistTimer();
      return undefined;
    }

    clearPersistTimer();
    timerRef.current = window.setTimeout(() => {
      persistNow(project);
    }, delay);

    return clearPersistTimer;
  }, [clearPersistTimer, delay, disabled, persistNow, project, storageKey]);

  useEffect(() => clearPersistTimer, [clearPersistTimer]);

  return persistNow;
}
