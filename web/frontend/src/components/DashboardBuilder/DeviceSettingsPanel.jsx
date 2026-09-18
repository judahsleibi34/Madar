import { useCallback, useEffect, useMemo, useState } from "react";
import { BellOff, BellRing, Download, Laptop, Smartphone, Trash2 } from "lucide-react";

import PageDeleteConfirmModal from "../PageBuilder/modals/PageDeleteConfirmModal";
import { getInstallationContext, getInstallationId, registerInstallation } from "../../pwa/installation";
import { useInstallPrompt } from "../../pwa/useInstallPrompt";
import { getMadarServiceWorkerRegistration } from "../../pwa/serviceWorker";
import {
  disableCurrentInstallationNotifications,
  listInstallations,
  revokeInstallation,
} from "../../services/installationsApi";
import {
  enableBrowserPushNotifications,
  getPushPublicKey,
} from "../../services/notificationsApi";
import {
  getDeviceDisplayLabel,
  getDeviceNotificationState,
  getDevicePlatformLabel,
} from "./deviceSettings";

const PLATFORM_ICONS = new Set(["ios", "android"]);

function formatLastSeen(value, language, copy) {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) return copy.unknownLastActive;
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const day = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const difference = Math.round((today - day) / 86400000);
  if (difference === 0) return copy.today;
  if (difference === 1) return copy.yesterday;
  return new Intl.DateTimeFormat(language === "ar" ? "ar" : "en", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(date);
}

function DeviceCard({ device, copy, lang, browserPermission, busy, onRemove, onEnable, onDisable, showNotificationControls }) {
  const MobileIcon = PLATFORM_ICONS.has(device.platform) ? Smartphone : Laptop;
  const notificationState = getDeviceNotificationState(device, browserPermission, copy);
  const canEnable = showNotificationControls && device.is_current && notificationState.key !== "enabled" && notificationState.key !== "blocked";
  const canDisable = showNotificationControls && device.is_current && notificationState.key === "enabled";

  return (
    <article className={`device-settings-item${device.is_current ? " is-current" : ""}`}>
      <div className="device-settings-icon" aria-hidden="true"><MobileIcon size={22} /></div>
      <div className="device-settings-copy">
        <div className="device-settings-heading">
          <h3>{getDevicePlatformLabel(device.platform, copy)}</h3>
          {device.is_current && <span>{copy.currentDevice}</span>}
        </div>
        <p>{getDeviceDisplayLabel(device.display_mode, copy)}</p>
        <p className={`device-settings-status is-${notificationState.key}`}>
          {notificationState.key === "enabled" ? <BellRing size={15} /> : <BellOff size={15} />}
          {notificationState.label}
        </p>
        <small>{copy.lastActive}: {formatLastSeen(device.last_seen_at, lang, copy)}</small>
        {device.is_current && notificationState.key === "blocked" && (
          <small className="device-settings-guidance">{copy.permissionBlockedGuidance}</small>
        )}
      </div>
      {(canEnable || canDisable || !device.is_current) && <div className="device-settings-actions">
        {canEnable && (
          <button type="button" className="settings-save-button" disabled={busy} onClick={onEnable}>
            <BellRing size={16} /> {copy.enableNotifications}
          </button>
        )}
        {canDisable && (
          <button type="button" className="device-settings-secondary" disabled={busy} onClick={onDisable}>
            <BellOff size={16} /> {copy.disableNotifications}
          </button>
        )}
        {!device.is_current && (
          <button type="button" className="device-settings-danger" disabled={busy} onClick={() => onRemove(device)}>
            <Trash2 size={16} /> {copy.removeDevice}
          </button>
        )}
      </div>}
    </article>
  );
}

export default function DeviceSettingsPanel({ lang = "en", tenantId, copy, showNotification, notificationsOnly = false }) {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");
  const [removeTarget, setRemoveTarget] = useState(null);
  const [installError, setInstallError] = useState("");
  const [pushConfig, setPushConfig] = useState(null);
  const installationId = useMemo(() => getInstallationId(), []);
  const localContext = useMemo(() => getInstallationContext(), []);
  const browserPermission = globalThis.Notification?.permission || "unknown";

  const loadDevices = useCallback(async () => {
    if (!installationId) return;
    setError("");
    try {
      const rows = await listInstallations(installationId);
      const ordered = [...rows].sort((left, right) => {
        if (left.is_current !== right.is_current) return left.is_current ? -1 : 1;
        return new Date(right.last_seen_at || 0) - new Date(left.last_seen_at || 0);
      });
      setDevices(ordered);
    } catch (loadError) {
      setError(loadError.message || copy.loadError);
    } finally {
      setLoading(false);
    }
  }, [copy.loadError, installationId]);

  const handleInstalled = useCallback(async () => {
    if (tenantId) {
      await registerInstallation({ tenantId, force: true, installedConfirmed: true }).catch(() => null);
    }
    await loadDevices();
  }, [loadDevices, tenantId]);
  const install = useInstallPrompt({ onInstalled: handleInstalled });

  const promptInstall = async () => {
    setInstallError("");
    const result = await install.promptInstall();
    if (result.outcome === "error") {
      setInstallError(copy.installError);
      showNotification?.("error", copy.installError);
    }
  };

  useEffect(() => {
    if (!install.supportedHost) return undefined;
    const loadTimer = window.setTimeout(loadDevices, 0);
    if (notificationsOnly) getPushPublicKey().then(setPushConfig).catch(() => setPushConfig({ enabled: false }));
    return () => window.clearTimeout(loadTimer);
  }, [install.supportedHost, loadDevices, notificationsOnly]);

  useEffect(() => {
    const refreshOnFocus = () => loadDevices();
    window.addEventListener("focus", refreshOnFocus);
    return () => window.removeEventListener("focus", refreshOnFocus);
  }, [loadDevices]);

  const currentDevice = devices.find((device) => device.is_current);
  const renderedDevices = currentDevice || !installationId ? devices : [
    {
      id: "local-current-device",
      platform: localContext.platform,
      display_mode: localContext.displayMode,
      notification_permission: browserPermission,
      notifications_enabled: false,
      has_active_push_subscription: false,
      last_seen_at: new Date().toISOString(),
      is_current: true,
    },
    ...devices,
  ];

  const enableNotifications = async () => {
    setBusyId("current");
    try {
      const result = await enableBrowserPushNotifications({ tenantId, pushConfig });
      if (!result.enabled) throw new Error(copy.pushErrors?.[result.reason] || copy.enableError);
      showNotification?.("success", copy.notificationsEnabled);
      await loadDevices();
    } catch (enableError) {
      showNotification?.("error", enableError.message || copy.enableError);
    } finally {
      setBusyId("");
    }
  };

  const disableNotifications = async () => {
    if (!installationId) return;
    setBusyId("current");
    try {
      await disableCurrentInstallationNotifications(installationId);
      const registration = await getMadarServiceWorkerRegistration().catch(() => null);
      const subscription = await registration?.pushManager?.getSubscription?.();
      await subscription?.unsubscribe?.().catch(() => false);
      showNotification?.("success", copy.notificationsDisabled);
      await loadDevices();
    } catch (disableError) {
      showNotification?.("error", disableError.message || copy.disableError);
    } finally {
      setBusyId("");
    }
  };

  const confirmRemove = async () => {
    const target = removeTarget;
    if (!target) return;
    setBusyId(target.id);
    try {
      await revokeInstallation(target.id);
      setDevices((current) => current.filter((device) => device.id !== target.id));
      setRemoveTarget(null);
      showNotification?.("success", copy.deviceRemoved);
    } catch (removeError) {
      showNotification?.("error", removeError.message || copy.removeError);
    } finally {
      setBusyId("");
    }
  };

  if (!install.supportedHost) return null;

  return (
    <div className="device-settings-panel">
      <section className="settings-card device-settings-card" aria-labelledby={notificationsOnly ? "browser-notifications-title" : "devices-title"}>
        <header>
          <div><h2 id={notificationsOnly ? "browser-notifications-title" : "devices-title"}>{notificationsOnly ? copy.browserNotificationsTitle : copy.devicesTitle}</h2><p>{notificationsOnly ? copy.browserNotificationsDescription : copy.devicesDescription}</p></div>
        </header>
        {loading && (
          <div className="device-settings-skeleton" aria-label={copy.loading} role="status">
            {[0, 1, 2].map((item) => (
              <div key={item} className="device-skeleton-row" aria-hidden="true">
                <span className="device-skeleton-icon" />
                <div className="device-skeleton-copy">
                  <i className="device-skeleton-title" />
                  <i className="device-skeleton-line" />
                  <i className="device-skeleton-line is-short" />
                </div>
                <span className="device-skeleton-action" />
              </div>
            ))}
          </div>
        )}
        {error && <p className="device-settings-message is-error" role="alert">{error}</p>}
        {!loading && !error && (
          <div className="device-settings-list">
            {renderedDevices.filter((device) => !notificationsOnly || device.is_current).map((device) => (
              <DeviceCard
                key={device.id}
                device={device}
                copy={copy}
                lang={lang}
                browserPermission={browserPermission}
                busy={Boolean(busyId)}
                onRemove={setRemoveTarget}
                onEnable={enableNotifications}
                onDisable={disableNotifications}
                showNotificationControls={notificationsOnly}
              />
            ))}
          </div>
        )}
      </section>

      {!notificationsOnly && <section className="settings-card device-settings-card device-install-card" aria-labelledby="install-madar-title">
        <div className="device-settings-icon" aria-hidden="true"><Download size={22} /></div>
        <div>
          <h2 id="install-madar-title">{copy.installMadar}</h2>
          {install.installState === "installed" ? (
            <p>{copy.alreadyInstalled}</p>
          ) : install.installState === "ios_manual" ? (
            <p>{copy.iosInstallGuidance}</p>
          ) : install.installState === "prompt_available" ? (
            <p>{copy.installDescription}</p>
          ) : install.installState === "manual_install_available" ? (
            <p>{copy.browserInstallGuidance}</p>
          ) : (
            <p>{copy.installUnavailable}</p>
          )}
          {installError ? <small role="alert">{installError}</small> : null}
        </div>
        {install.canPrompt && (
          <button
            type="button"
            className="settings-save-button"
            disabled={install.isPrompting}
            onClick={promptInstall}
          >
            <Download size={16} /> {install.isPrompting ? copy.installing : copy.installMadar}
          </button>
        )}
      </section>}

      {removeTarget && (
        <PageDeleteConfirmModal
          lang={lang}
          icon={<Trash2 size={24} />}
          title={copy.removeConfirmTitle}
          message={copy.removeConfirmMessage}
          cancelLabel={copy.cancel}
          confirmLabel={copy.removeDevice}
          confirmDisabled={Boolean(busyId)}
          onCancel={() => setRemoveTarget(null)}
          onConfirm={confirmRemove}
        />
      )}
    </div>
  );
}
