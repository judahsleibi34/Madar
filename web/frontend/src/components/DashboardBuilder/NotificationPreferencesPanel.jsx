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

  return (
    <section className="settings-card" aria-labelledby="notification-preferences-title">
      <header>
        <h2 id="notification-preferences-title">{copy.title}</h2>
        <p>{copy.description}</p>
      </header>
      {loading ? <p>{copy.loading}</p> : null}
      {error ? <p role="alert">{error}</p> : null}
      {!loading && !error ? (
        <div className="settings-form-grid">
          {rows.map((preference) => {
            const key = `${preference.category}:${preference.channel}`;
            return (
              <label key={key} className="settings-wide-field">
                <span>{copy.categories[preference.category]} — {copy.channels[preference.channel]}</span>
                <input
                  type="checkbox"
                  checked={Boolean(preference.enabled)}
                  disabled={saving === key}
                  onChange={() => update(preference)}
                />
              </label>
            );
          })}
        </div>
      ) : null}
      <small>{copy.deviceNote}</small>
    </section>
  );
}
