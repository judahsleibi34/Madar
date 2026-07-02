import { Bell, CheckCircle2, Circle } from "lucide-react";

import { useLanguage } from "../../i18n";
import { getDummyNotifications } from "./notificationsData";

export default function NotificationsPage() {
  const { direction, t } = useLanguage();
  const dummyNotifications = getDummyNotifications(t);
  const unreadCount = dummyNotifications.filter((item) => item.unread).length;
  const groupedNotifications = dummyNotifications.reduce((groups, item) => {
    const key = item.group || t("notifications.groups.earlier");
    return {
      ...groups,
      [key]: [...(groups[key] || []), item],
    };
  }, {});

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

      <div
        className="notifications-summary-grid"
        aria-label={t("notifications.summary")}
      >
        <article>
          <span>{t("notifications.total")}</span>
          <strong>{dummyNotifications.length}</strong>
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
