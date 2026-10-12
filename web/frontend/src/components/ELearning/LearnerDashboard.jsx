import { useContext, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { fetchMyLearning } from "../../services/elearningPlayer";
import { NotificationContext } from "../../notifications/NotificationContext";
import ELearningSkeleton from "./ELearningSkeleton";

export default function LearnerDashboard() {
  const { t, i18n } = useTranslation("dashboard");
  const notifications = useContext(NotificationContext);
  const [state, setState] = useState({ loading: true });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => { let active = true; fetchMyLearning().then(data => { if (active) setState({ data }); }).catch(() => { if (active) setState({ error: true }); }); return () => { active = false; }; }, [attempt]);
  if (state.loading) return <ELearningSkeleton label={t("elearning.player.loading")} direction={i18n.dir()} />;
  if (state.error) return <div role="alert"><p>{t("elearning.player.loadError")}</p><button className="ecommerce-secondary-button" onClick={() => { setState({ loading: true }); setAttempt(value => value + 1); }}>{t("elearning.retry")}</button></div>;
  const courses = state.data.courses || [];
  return <section className="learner-dashboard"><header className="ecommerce-page-header"><div><h1>{t("elearning.academy.home")}</h1><p>{t("elearning.player.intro")}</p></div></header>
    <section className="learner-account-panel"><h2>{t("elearning.player.continue")}</h2>{!courses.length && <p>{t("elearning.player.empty")}</p>}{courses.length > 0 && courses.every(row => row.progress?.completion?.completed === true) && <p>{t("elearning.player.completed")}</p>}<ul className="learner-dashboard-courses">{courses.filter(row => row.continue_lesson_id || row.continue_assessment_id || row.progress?.completion?.completed !== true).slice(0, 4).map(row => <li key={row.course.id}><div><h3>{row.course.name}</h3><p>{row.progress.progress_percent}% · {row.progress.completed_lessons} / {row.progress.total_lessons}</p></div><Link className="ecommerce-primary-button" to={`/my-learning/courses/${row.course.id}${row.continue_lesson_id ? `/lessons/${row.continue_lesson_id}` : row.continue_assessment_id ? `/assessments/${row.continue_assessment_id}` : ''}`}>{t(row.continue_lesson_id || row.continue_assessment_id ? "elearning.player.continue" : "elearning.player.reviewCourse")}</Link></li>)}</ul><Link className="ecommerce-secondary-button" to="/my-learning">{t("elearning.player.myLearning")}</Link></section>
    <nav className="learner-dashboard-actions" aria-label={t("elearning.academy.navigation")}><Link className="learner-account-panel" to="/my-learning/certificates">{t("elearning.certificates.myCertificates")}</Link><Link className="learner-account-panel" to="/my-learning/notifications">{t("sidebar.notifications")}{notifications?.unreadCount > 0 && <span className="learning-unread-count">{notifications.unreadCount}</span>}</Link><Link className="learner-account-panel" to="/my-learning/account">{t("elearning.learner.account")}</Link></nav>
  </section>;
}
