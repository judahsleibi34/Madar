import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Bell } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { useLanguage } from "../../i18n";
import {
  fetchNotifications,
} from "../../services/notificationsApi";

const NOTIFICATION_POLL_MS = 15_000;
const MOBILE_SIDEBAR_QUERY = "(max-width: 900px)";
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
  unread: item.unread !== false,
});

export default function NotificationBell({
  className = "",
  compact = false,
  label,
  onNavigate,
  tenantId,
  userId,
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useLanguage();
  const bellRef = useRef(null);
  const buttonRef = useRef(null);
  const panelRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [panelPosition, setPanelPosition] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loadedIdentity, setLoadedIdentity] = useState("");
  const notificationIdentity = `${tenantId || ""}:${userId || ""}`;
  const identityMatches = loadedIdentity === notificationIdentity;
  const visibleNotifications = identityMatches ? notifications : EMPTY_NOTIFICATIONS;
  const visibleUnreadCount = identityMatches ? unreadCount : 0;
  const active = location.pathname.startsWith("/notifications");
  const resolvedLabel = label || t("notifications.title");

  useEffect(() => {
    let cancelled = false;
    let requestInFlight = false;
    let activeController = null;

    if (!tenantId || !userId) {
      return () => {
        cancelled = true;
      };
    }

    const loadNotifications = async () => {
      if (requestInFlight) return;
      requestInFlight = true;
      activeController = new AbortController();
      try {
        const data = await fetchNotifications({ limit: 4, signal: activeController.signal });
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
        requestInFlight = false;
        activeController = null;
      }
    };

    loadNotifications();
    const poll = () => {
      if (document.visibilityState !== "hidden") loadNotifications();
    };
    const interval = window.setInterval(poll, NOTIFICATION_POLL_MS);
    window.addEventListener("focus", poll);
    document.addEventListener("visibilitychange", poll);

    return () => {
      cancelled = true;
      activeController?.abort();
      window.clearInterval(interval);
      window.removeEventListener("focus", poll);
      document.removeEventListener("visibilitychange", poll);
    };
  }, [notificationIdentity, t, tenantId, userId]);

  const getPanelPosition = useCallback((rect) => {
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const panelWidth = Math.max(280, Math.min(330, viewportWidth - 24));
    const panelHeight = Math.min(520, viewportHeight - 32);

    if (viewportWidth <= 760) {
      return {
        top: 76,
        left: 12,
        width: viewportWidth - 24,
      };
    }

    const isRtl =
      document.documentElement.dir === "rtl" || document.body.dir === "rtl";
    const preferredLeft = isRtl
      ? rect.left - panelWidth - 12
      : rect.right + 12;
    const left = Math.max(
      12,
      Math.min(preferredLeft, viewportWidth - panelWidth - 12),
    );
    const top = Math.max(
      16,
      Math.min(rect.top, viewportHeight - panelHeight - 16),
    );

    return { top, left, width: panelWidth };
  }, []);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const handlePointerDown = (event) => {
      if (
        bellRef.current?.contains(event.target) ||
        panelRef.current?.contains(event.target)
      ) {
        return;
      }

      setOpen(false);
    };

    const handleKeyDown = (event) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const positionPanel = () => {
      const rect = buttonRef.current?.getBoundingClientRect();

      if (!rect) {
        return;
      }

      setPanelPosition(getPanelPosition(rect));
    };

    window.addEventListener("resize", positionPanel);
    window.addEventListener("scroll", positionPanel, true);

    return () => {
      window.removeEventListener("resize", positionPanel);
      window.removeEventListener("scroll", positionPanel, true);
    };
  }, [getPanelPosition, open]);

  const togglePanel = (event) => {
    const triggerRect = event.currentTarget.getBoundingClientRect();

    setOpen((current) => {
      const nextOpen = !current;

      if (nextOpen) {
        setPanelPosition(getPanelPosition(triggerRect));
      } else {
        setPanelPosition(null);
      }

      return nextOpen;
    });
  };

  const viewAllNotifications = () => {
    setOpen(false);
    setPanelPosition(null);
    navigate("/notifications");

    if (typeof onNavigate === "function") {
      onNavigate();
    }
  };

  const handleBellClick = (event) => {
    if (window.matchMedia?.(MOBILE_SIDEBAR_QUERY).matches) {
      viewAllNotifications();
      return;
    }

    togglePanel(event);
  };

  return (
    <div
      className={[
        "notification-bell",
        compact ? "is-compact" : "",
        active ? "is-active" : "",
        open ? "is-open" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      ref={bellRef}
    >
      <button
        type="button"
        className="notification-bell-button"
        onClick={handleBellClick}
        aria-label={resolvedLabel}
        aria-expanded={open}
        aria-haspopup="dialog"
        title={resolvedLabel}
        ref={buttonRef}
      >
        <Bell size={compact ? 18 : 20} aria-hidden="true" />
        {visibleUnreadCount > 0 && (
          <span className="notification-bell-badge">{visibleUnreadCount}</span>
        )}
        {!compact && (
          <span className="notification-bell-label">{resolvedLabel}</span>
        )}
      </button>

      {open &&
        createPortal(
        <section
          className="notification-popover"
          aria-label={t("notifications.ariaRecent")}
          ref={panelRef}
          style={
            panelPosition
              ? {
                  top: `${panelPosition.top}px`,
                  left: `${panelPosition.left}px`,
                  width: `${panelPosition.width}px`,
                }
              : undefined
          }
        >
          <div className="notification-popover-header">
            <strong>{resolvedLabel}</strong>
            <span>{t("notifications.unreadCount", { count: visibleUnreadCount })}</span>
          </div>

          <div className="notification-popover-list">
            {visibleNotifications.slice(0, 4).map((item) => (
              <article
                className={item.unread ? "is-unread" : ""}
                key={item.id}
              >
                <span className="notification-popover-dot" aria-hidden="true" />
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.detail}</p>
                  <time>{item.time}</time>
                </div>
              </article>
            ))}
          </div>

          <button
            type="button"
            className="notification-popover-view-all"
            onClick={viewAllNotifications}
          >
            {t("notifications.viewAll")}
          </button>
        </section>,
        document.body,
      )}
    </div>
  );
}
