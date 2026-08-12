import { useCallback, useEffect, useState } from "react";

import { getMadarLaunchContext, isIOSDevice, isMadarPwaHost } from "./pwaContext";

export function useInstallPrompt({ onInstalled, windowLike = globalThis.window } = {}) {
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [isStandalone, setIsStandalone] = useState(
    () => getMadarLaunchContext(windowLike).isStandalone
  );
  const supportedHost = isMadarPwaHost(windowLike?.location);
  const isIOS = supportedHost && isIOSDevice(windowLike);

  useEffect(() => {
    if (!supportedHost || !windowLike?.addEventListener) return undefined;

    const handleBeforeInstallPrompt = (event) => {
      event.preventDefault();
      if (!getMadarLaunchContext(windowLike).isStandalone) {
        setDeferredPrompt(event);
      }
    };
    const handleInstalled = () => {
      setDeferredPrompt(null);
      setIsStandalone(true);
      onInstalled?.();
    };

    windowLike.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
    windowLike.addEventListener("appinstalled", handleInstalled);
    return () => {
      windowLike.removeEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
      windowLike.removeEventListener("appinstalled", handleInstalled);
    };
  }, [onInstalled, supportedHost, windowLike]);

  const promptInstall = useCallback(async () => {
    if (!deferredPrompt || isStandalone) return { outcome: "unavailable" };
    const promptEvent = deferredPrompt;
    setDeferredPrompt(null);
    await promptEvent.prompt();
    return promptEvent.userChoice || { outcome: "dismissed" };
  }, [deferredPrompt, isStandalone]);

  return {
    canPrompt: supportedHost && !isStandalone && !isIOS && Boolean(deferredPrompt),
    isIOS,
    isStandalone,
    promptInstall,
    supportedHost,
  };
}
