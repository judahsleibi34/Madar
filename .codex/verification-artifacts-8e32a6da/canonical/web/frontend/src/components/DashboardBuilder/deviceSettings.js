export function getDevicePlatformLabel(platform, copy) {
  return copy.platforms?.[platform] || copy.platforms?.unknown || copy.browserDevice;
}

export function getDeviceDisplayLabel(displayMode, copy) {
  return displayMode === "standalone" || displayMode === "ios_standalone"
    ? copy.installedApp
    : copy.browser;
}

export function getDeviceNotificationState(device, browserPermission, copy) {
  if (device.is_current && browserPermission === "denied") {
    return { key: "blocked", label: copy.notificationsBlocked };
  }
  if (device.notification_permission === "denied") {
    return { key: "blocked", label: copy.notificationsBlocked };
  }
  if (device.notifications_enabled && device.has_active_push_subscription) {
    return { key: "enabled", label: copy.notificationsEnabled };
  }
  if (device.notifications_enabled) {
    return { key: "missing", label: copy.noActiveSubscription };
  }
  return { key: "disabled", label: copy.notificationsDisabled };
}
