import { useEffect, useMemo, useState } from "react";
import { fetchWeeklyScreenTime } from "../PageBuilder/services/PageBuilder.api";
import { formatWeeklyScreenTime } from "../../hooks/useWeeklyScreenTime";
import {
  getDashboardCacheScope,
  readScreenTimeCache,
  writeScreenTimeCache,
} from "./utils/dashboardSnapshotCache";
import "../../styles/admin/dashboard/weekly-screen-time.css";

const PERIODS = [
  { id: "today", label: "Today", title: "Today’s activity", note: "Today so far" },
  { id: "week", label: "Last 7 days", title: "Weekly activity", note: "Rolling 7-day total" },
  { id: "month", label: "This month", title: "Monthly activity", note: "Current calendar month" },
];

function getDisplayName(user) {
  return (
    user?.name ||
    [user?.first_name, user?.last_name].filter(Boolean).join(" ") ||
    user?.email?.split?.("@")?.[0] ||
    "Current user"
  );
}

export default function WeeklyScreenTimePanel({
  currentUser = null,
  currentSeconds = 0,
  projectId = "",
}) {
  const [period, setPeriod] = useState("week");
  const cacheScope = getDashboardCacheScope(currentUser);
  const initialSummary = readScreenTimeCache(cacheScope, projectId, "week");
  const [summary, setSummary] = useState(
    () => initialSummary || { users: [], total_seconds: 0 },
  );
  const [loading, setLoading] = useState(() => !initialSummary);
  const selectedPeriod = PERIODS.find((item) => item.id === period) || PERIODS[1];

  useEffect(() => {
    let cancelled = false;

    const loadSummary = async () => {
      const cachedSummary = readScreenTimeCache(cacheScope, projectId, period);
      if (cachedSummary) {
        setSummary(cachedSummary);
        setLoading(false);
      } else {
        setLoading(true);
      }
      try {
        const nextSummary = await fetchWeeklyScreenTime(projectId, period);
        if (!cancelled) {
          const safeSummary = nextSummary || { users: [], total_seconds: 0 };
          writeScreenTimeCache(cacheScope, projectId, period, safeSummary);
          setSummary(safeSummary);
        }
      } catch {
        if (!cancelled && !cachedSummary) setSummary({ users: [], total_seconds: 0 });
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadSummary();
    const intervalId = window.setInterval(loadSummary, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [cacheScope, period, projectId]);

  const users = useMemo(() => {
    const currentUserId = String(currentUser?.id || currentUser?.auth_id || "");
    const rows = (summary.users || []).map((item) => ({
      ...item,
      active_seconds:
        period !== "today" &&
        (item.is_current_user || String(item.user_id) === currentUserId)
          ? Math.max(Number(item.active_seconds) || 0, Number(currentSeconds) || 0)
          : Number(item.active_seconds) || 0,
    }));

    if (
      currentUserId &&
      !rows.some((item) => String(item.user_id) === currentUserId || item.is_current_user)
    ) {
      rows.push({
        user_id: currentUserId,
        name: getDisplayName(currentUser),
        role: "current user",
        active_seconds: period === "today" ? 0 : Number(currentSeconds) || 0,
        is_current_user: true,
      });
    }

    return rows.sort(
      (left, right) =>
        right.active_seconds - left.active_seconds ||
        String(left.name).localeCompare(String(right.name))
    );
  }, [currentSeconds, currentUser, period, summary.users]);

  const totalSeconds = users.reduce((total, item) => total + item.active_seconds, 0);
  const maxSeconds = Math.max(1, ...users.map((item) => item.active_seconds));

  return (
    <section className="weekly-screen-time-panel" aria-labelledby="weekly-screen-time-title">
      <header className="weekly-screen-time-header">
        <div>
          <h2 id="weekly-screen-time-title">{selectedPeriod.title}</h2>
          <p>Focused time for admins and role-assigned users.</p>
        </div>
        <div className="weekly-screen-time-period" role="tablist" aria-label="Reporting period">
          {PERIODS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={period === item.id}
              className={period === item.id ? "is-active" : ""}
              onClick={() => setPeriod(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </header>

      <div className="weekly-screen-time-content">
        <div className="weekly-screen-time-total">
          <span>All users</span>
          <strong>{formatWeeklyScreenTime(totalSeconds)}</strong>
          <small>{selectedPeriod.note}</small>
        </div>

        <div className="weekly-screen-time-bars" aria-busy={loading}>
          {users.length ? (
            users.map((item) => {
              const percent = Math.round((item.active_seconds / maxSeconds) * 100);
              return (
                <article className="weekly-screen-time-user" key={item.user_id}>
                  <div className="weekly-screen-time-user-heading">
                    <div>
                      <strong>{item.name}</strong>
                      <span>{item.role || "member"}</span>
                    </div>
                    <b>{formatWeeklyScreenTime(item.active_seconds)}</b>
                  </div>
                  <div
                    className="weekly-screen-time-track"
                    role="progressbar"
                    aria-label={item.name + " " + period + " screen time"}
                    aria-valuemin="0"
                    aria-valuemax={maxSeconds}
                    aria-valuenow={item.active_seconds}
                  >
                    <span style={{ width: percent + "%" }} />
                  </div>
                </article>
              );
            })
          ) : (
            <p className="weekly-screen-time-empty">
              {loading ? "Loading user activity…" : "No assigned users yet."}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}