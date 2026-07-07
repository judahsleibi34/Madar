import { useEffect, useMemo, useState } from "react";
import { Bell, CheckCircle2, Circle } from "lucide-react";

import { useLanguage } from "../../i18n";
import {
  enableBrowserPushNotifications,
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../../services/notificationsApi";
import { getDummyNotifications } from "./notificationsData";

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

export default function NotificationsPage() {
  const { direction, t } = useLanguage();
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [pushState, setPushState] = useState("");

  useEffect(() => {
    let cancelled = false;

    const loadNotifications = async () => {
      setLoading(true);

      try {
        const data = await fetchNotifications({ limit: 50 });
        const items = (data.notifications || data.items || []).map((item) =>
          normalizeNotification(item, t)
        );

        if (cancelled) return;

        setNotifications(items);
        setUnreadCount(Number(data.unread_count || 0));
      } catch {
        if (cancelled) return;
        const fallback = getDummyNotifications(t);
        setNotifications(fallback);
        setUnreadCount(fallback.filter((item) => item.unread).length);
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadNotifications();

    return () => {
      cancelled = true;
    };
  }, [t]);

  const groupedNotifications = useMemo(() => notifications.reduce((groups, item) => {
    const key = item.group || t("notifications.groups.earlier");
    return {
      ...groups,
      [key]: [...(groups[key] || []), item],
    };
  }, {}), [notifications, t]);

  const enablePush = async () => {
    setPushState("loading");

    try {
      const result = await enableBrowserPushNotifications();
      setPushState(result.enabled ? "enabled" : result.reason || "unavailable");
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
          aria-label={t("notifications.unreadCount", { count: unreadCount })}
        >
          <Bell size={18} aria-hidden="true" />
          <strong>{unreadCount}</strong>
          <span>{t("notifications.unread")}</span>
        </div>
      </header>

      <div className="notifications-actions">
        <button type="button" onClick={enablePush} disabled={pushState === "loading"}>
          {t("notifications.enablePush")}
        </button>
        <button type="button" onClick={markAllRead} disabled={unreadCount === 0}>
          {t("notifications.markAllRead")}
        </button>
        {pushState && (
          <span>{t(`notifications.pushState.${pushState}`)}</span>
        )}
      </div>

      <div
        className="notifications-summary-grid"
        aria-label={t("notifications.summary")}
      >
        <article>
          <span>{t("notifications.total")}</span>
          <strong>{notifications.length}</strong>
        </article>
        <article>
          <span>{t("notifications.unread")}</span>
          <strong>{unreadCount}</strong>
        </article>
        <article>
          <span>{t("notifications.sources")}</span>
          <strong>5</strong>
        </article>
      </div>

      <div className="notifications-board">
        {!loading && notifications.length === 0 && (
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
