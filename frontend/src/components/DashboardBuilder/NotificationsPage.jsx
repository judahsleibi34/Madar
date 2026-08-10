import { useEffect, useMemo, useState } from "react";
import { Bell, CheckCircle2, Circle } from "lucide-react";

import { useLanguage } from "../../i18n";
import { isAndroidDevice } from "../../pwa/pwaContext";
import {
  enableBrowserPushNotifications,
  fetchNotifications,
  getBrowserPushStatus,
  markAllNotificationsRead,
  markNotificationRead,
} from "../../services/notificationsApi";

const EMPTY_NOTIFICATIONS = [];

const formatNotificationTime = (value) => {
  if (!value) return "";

  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return String(value);
  }
};

const normalizeNotification = (item, t) => ({
  id: item.id,
  title: item.title || t("notifications.fallbackTitle"),
  detail: item.body || item.detail || "",
  time: item.time || formatNotificationTime(item.created_at),
  group: item.group || t("notifications.groups.today"),
  source: item.source || item.event_type || t("notifications.sourcesList.system"),
  unread: item.unread !== false,
});

export default function NotificationsPage({ user }) {
  const { direction, t } = useLanguage();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [pushState, setPushState] = useState("checking");
  const [loadedIdentity, setLoadedIdentity] = useState("");
  const notificationIdentity = `${user?.tenant_id || ""}:${user?.id || user?.auth_id || ""}`;
  const hasNotificationIdentity = Boolean(user?.tenant_id && (user?.id || user?.auth_id));
  const identityMatches = loadedIdentity === notificationIdentity;
  const visibleNotifications = identityMatches ? notifications : EMPTY_NOTIFICATIONS;
  const visibleUnreadCount = identityMatches ? unreadCount : 0;
  const visibleLoading = hasNotificationIdentity && (identityMatches ? loading : true);

  useEffect(() => {
    let cancelled = false;
    getBrowserPushStatus()
      .then((result) => {
        if (cancelled) return;
        setPushState(
          result.enabled
            ? isAndroidDevice() ? "android_enabled" : "enabled"
            : result.reason === "subscription_missing" ? "" : result.reason || ""
        );
      })
      .catch(() => {
        if (!cancelled) setPushState("");
      });
    return () => {
      cancelled = true;
    };
  }, [notificationIdentity]);

  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();

    if (!hasNotificationIdentity) {
      return () => {
        cancelled = true;
      };
    }

    const loadNotifications = async () => {
      setLoading(true);

      try {
        const data = await fetchNotifications({ limit: 50, signal: controller.signal });
        const items = (data.notifications || data.items || []).map((item) =>
          normalizeNotification(item, t)
        );

        if (cancelled) return;

        setNotifications(items);
        setUnreadCount(Number(data.unread_count || 0));
        setLoadedIdentity(notificationIdentity);
      } catch (error) {
        if (cancelled) return;
        if (error?.name !== "AbortError") {
          setNotifications([]);
          setUnreadCount(0);
          setLoadedIdentity(notificationIdentity);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadNotifications();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [hasNotificationIdentity, notificationIdentity, t, user?.auth_id, user?.id, user?.tenant_id]);

  const groupedNotifications = useMemo(() => visibleNotifications.reduce((groups, item) => {
    const key = item.group || t("notifications.groups.earlier");
    return {
      ...groups,
      [key]: [...(groups[key] || []), item],
    };
  }, {}), [visibleNotifications, t]);
  const visibleSourceCount = useMemo(
    () => new Set(visibleNotifications.map((item) => item.source).filter(Boolean)).size,
    [visibleNotifications],
  );

  const enablePush = async () => {
    setPushState("loading");

    try {
      const result = await enableBrowserPushNotifications({ tenantId: user?.tenant_id });
      setPushState(
        result.enabled
          ? isAndroidDevice() ? "android_enabled" : "enabled"
          : result.reason || "unavailable"
      );
    } catch {
      setPushState("failed");
    }
  };

  const markOneRead = async (item) => {
    if (!item.unread) return;

    try {
      await markNotificationRead(item.id);
      setNotifications((current) =>
        current.map((candidate) =>
          candidate.id === item.id ? { ...candidate, unread: false } : candidate
        )
      );
      setUnreadCount((current) => Math.max(0, current - 1));
    } catch {
      // Keep the current UI state; a later refresh will reconcile it.
    }
  };

  const markAllRead = async () => {
    try {
      await markAllNotificationsRead();
      setNotifications((current) => current.map((item) => ({ ...item, unread: false })));
      setUnreadCount(0);
    } catch {
      // Keep the current UI state; a later refresh will reconcile it.
    }
  };

  return (
    <section
      className="notifications-page"
      aria-labelledby="notifications-title"
      dir={direction}
    >
      <header className="notifications-page-header">
        <div>
          <span className="notifications-kicker">
            {t("notifications.kicker")}
          </span>
          <h1 id="notifications-title">{t("notifications.title")}</h1>
          <p>{t("notifications.subtitle")}</p>
        </div>

        <div
          className="notifications-header-count"
          aria-label={t("notifications.unreadCount", { count: visibleUnreadCount })}
        >
          <Bell size={18} aria-hidden="true" />
          <strong>{visibleUnreadCount}</strong>
          <span>{t("notifications.unread")}</span>
        </div>
      </header>

      <div className="notifications-actions">
        <button
          type="button"
          onClick={enablePush}
          disabled={["checking", "loading", "enabled", "android_enabled"].includes(pushState)}
        >
          {pushState === "enabled" || pushState === "android_enabled"
            ? t("notifications.pushEnabledButton")
            : t("notifications.enablePush")}
        </button>
        <button type="button" onClick={markAllRead} disabled={visibleUnreadCount === 0}>
          {t("notifications.markAllRead")}
        </button>
        {pushState && (
          <span role="status">{t(`notifications.pushState.${pushState}`)}</span>
        )}
      </div>

      <div
        className="notifications-summary-grid"
        aria-label={t("notifications.summary")}
      >
        <article>
          <span>{t("notifications.total")}</span>
          <strong>{visibleNotifications.length}</strong>
        </article>
        <article>
          <span>{t("notifications.unread")}</span>
          <strong>{visibleUnreadCount}</strong>
        </article>
        <article>
          <span>{t("notifications.sources")}</span>
          <strong>{visibleSourceCount}</strong>
        </article>
      </div>

      <div className="notifications-board">
        {!visibleLoading && visibleNotifications.length === 0 && (
          <section className="notifications-group">
            <div className="notifications-list">
              <article>
                <div className="notifications-copy">
                  <h3>{t("notifications.emptyTitle")}</h3>
                  <p>{t("notifications.emptyDetail")}</p>
                </div>
              </article>
            </div>
          </section>
        )}

        {Object.entries(groupedNotifications).map(([group, items]) => (
          <section className="notifications-group" key={group}>
            <div className="notifications-group-header">
              <h2>{group}</h2>
              <span>{t("notifications.items", { count: items.length })}</span>
            </div>

            <div className="notifications-list">
              {items.map((item) => (
                <article
                  className={item.unread ? "is-unread" : ""}
                  key={item.id}
                  onClick={() => markOneRead(item)}
                >
                  <div className="notifications-status" aria-hidden="true">
                    {item.unread ? <Circle size={12} /> : <CheckCircle2 size={16} />}
                  </div>

                  <div className="notifications-copy">
                    <div className="notifications-title-row">
                      <h3>{item.title}</h3>
                      <span>{item.source}</span>
                    </div>
                    <p>{item.detail}</p>
                    <time>{item.time}</time>
                  </div>

                  <span className="notifications-state">
                    {item.unread
                      ? t("notifications.unread")
                      : t("notifications.read")}
                  </span>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}
