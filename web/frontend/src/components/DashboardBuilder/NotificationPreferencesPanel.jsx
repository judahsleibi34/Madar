import { useCallback, useEffect, useState } from "react";

import {
  fetchNotificationPreferences,
  saveNotificationPreference,
} from "../../services/notificationsApi";

const CATEGORY_ORDER = ["calendar", "reservations", "forms", "general"];
const CHANNEL_ORDER = ["in_app", "push", "email"];

export default function NotificationPreferencesPanel({ copy, showNotification }) {
  const [preferences, setPreferences] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      setPreferences(await fetchNotificationPreferences());
    } catch (loadError) {
      setError(loadError.message || copy.loadError);
    } finally {
      setLoading(false);
    }
  }, [copy.loadError]);

  useEffect(() => {
    // Schedule the initial fetch after mount so React does not synchronously
    // cascade local state updates during the effect commit.
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const update = async (preference) => {
    const key = `${preference.category}:${preference.channel}`;
    setSaving(key);
    try {
      const saved = await saveNotificationPreference({ ...preference, enabled: !preference.enabled });
      setPreferences((current) => current.map((item) => (
        item.category === saved.category && item.channel === saved.channel
          ? { ...item, enabled: Boolean(saved.enabled) }
          : item
      )));
    } catch (saveError) {
      showNotification?.("error", saveError.message || copy.saveError);
    } finally {
      setSaving("");
    }
  };

  const rows = [...preferences].sort((left, right) => (
    CATEGORY_ORDER.indexOf(left.category) - CATEGORY_ORDER.indexOf(right.category)
    || CHANNEL_ORDER.indexOf(left.channel) - CHANNEL_ORDER.indexOf(right.channel)
  ));
  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    preferences: rows.filter((preference) => preference.category === category),
  })).filter((group) => group.preferences.length > 0);

  return (
    <section className="settings-card notification-preferences-card" aria-labelledby="notification-preferences-title">
      <header className="notification-preferences-header">
        <h2 id="notification-preferences-title">{copy.title}</h2>
        <p>{copy.description}</p>
      </header>
      {loading ? (
        <div className="notification-preferences-skeleton" aria-label={copy.loading} role="status">
          {[0, 1, 2, 3].map((item) => (
            <div key={item} className="notification-skeleton-card" aria-hidden="true">
              <span className="notification-skeleton-title" />
              {[0, 1, 2].map((row) => (
                <div key={row} className="notification-skeleton-row">
                  <i className="notification-skeleton-label" />
                  <i className="notification-skeleton-toggle" />
                </div>
              ))}
            </div>
          ))}
        </div>
      ) : null}
      {error ? <p className="notification-preferences-error" role="alert">{error}</p> : null}
      {!loading && !error ? (
        <div className="notification-preferences-grid">
          {groups.map((group) => (
            <article key={group.category} className="notification-preference-group">
              <h3>{copy.categories[group.category]}</h3>
              <div>
                {group.preferences.map((preference) => {
                  const key = `${preference.category}:${preference.channel}`;
                  return (
                    <label key={key} className="notification-preference-row">
                      <span>{copy.channels[preference.channel]}</span>
                      <span className="notification-preference-toggle">
                        <input
                          type="checkbox"
                          checked={Boolean(preference.enabled)}
                          disabled={saving === key}
                          onChange={() => update(preference)}
                        />
                        <span aria-hidden="true" />
                      </span>
                    </label>
                  );
                })}
              </div>
            </article>
          ))}
        </div>
      ) : null}
      <footer className="notification-preferences-note"><small>{copy.deviceNote}</small></footer>
    </section>
  );
}
