import { useEffect, useState } from "react";
import { apiFetch, getApiUrl } from "../../utils/apiClient";
import { Link } from "react-router-dom";
import { getAdminDashboardContent } from "../../content";

export default function Dashboard({ lang = "en", themeMode = "light" }) {
  const t = getAdminDashboardContent(lang);
  const [userCount, setUserCount] = useState(null);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    // Reuse the existing exact server count; fetch only one row, no per-user calls.
    apiFetch(getApiUrl("/admin/users?page=1&page_size=1"), { cache: "no-store", signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error("User count unavailable");
        const data = await response.json();
        const count = data.pagination?.total_count;
        if (active && Number.isInteger(count) && count >= 0) setUserCount(count);
      }).catch(() => { /* An unavailable count remains explicitly unavailable. */ });
    return () => { active = false; controller.abort(); };
  }, []);
  const unavailable = lang === "ar" ? "غير متاح — لم يتم توصيل مصدر بيانات موثوق." : "Not available — no authoritative metrics source is connected.";
  return <section className="dashboard-page admin-dashboard-shell" dir={lang === "ar" ? "rtl" : "ltr"} data-theme={themeMode}>
    <header className="admin-dashboard-header app-page-intro"><h1>{t.title}</h1></header>
    <section className="overview-grid">
      {[t.runningProjects, t.users, t.totalRevenue, t.uptime].map(title => <article className="overview-card navy" key={title}><h2>{title}</h2><p>{title === t.users && userCount !== null ? userCount.toLocaleString(lang === "ar" ? "ar" : "en") : unavailable}</p></article>)}
    </section>
    <article className="dashboard-panel"><h2>{lang === "ar" ? "إدارة المنصة" : "Platform Administration"}</h2>
      <p><Link to="/admin/users">Users / Tenants</Link></p>
      <p><Link to="/admin/account-access">Account Access</Link></p>
      <p><Link to="/settings/security">Security</Link></p>
    </article>
  </section>;
}
