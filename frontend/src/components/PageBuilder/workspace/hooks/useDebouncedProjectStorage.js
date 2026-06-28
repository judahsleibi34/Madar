import { useCallback, useEffect, useRef } from "react";

export default function useDebouncedProjectStorage({
  delay = 600,
  disabled = false,
  project,
  storageKey,
}) {
  const timerRef = useRef(null);
  const latestProjectRef = useRef(project);
  const lastSerializedRef = useRef("");

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
        lastSerializedRef.current = serializedProject;
      } catch (error) {
        console.warn("Could not persist builder draft:", error);
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
