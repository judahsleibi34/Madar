import { useCallback, useEffect, useSyncExternalStore } from "react";

import {
  getInstallPromptSnapshot,
  getInstallPromptState,
  initializeInstallPromptCapture,
  promptForInstall,
  subscribeAppInstalled,
  subscribeInstallPrompt,
} from "./installPromptStore";

export function useInstallPrompt({ onInstalled, windowLike = globalThis.window } = {}) {
  const storeSnapshot = useSyncExternalStore(
    subscribeInstallPrompt,
    getInstallPromptSnapshot,
    getInstallPromptSnapshot,
  );
  const state = getInstallPromptState(windowLike);

  useEffect(() => {
    initializeInstallPromptCapture(windowLike);
  }, [windowLike]);

  useEffect(() => subscribeAppInstalled(() => onInstalled?.()), [onInstalled]);

  const promptInstall = useCallback(async () => {
    return promptForInstall();
  }, []);

  return {
    canPrompt: state.status === "prompt_available",
    error: storeSnapshot.error,
    installState: state.status,
    isIOS: state.isIOS,
    isPrompting: storeSnapshot.prompting,
    isStandalone: state.installed,
    lastOutcome: storeSnapshot.lastOutcome,
    promptInstall,
    supportedHost: state.supportedHost,
  };
}
