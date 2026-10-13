import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Bell, BookOpen, ClipboardList, GraduationCap, Layers, Share2, TrendingUp, Wallet } from "lucide-react";
import { apiFetch, getApiUrl } from "../../../utils/apiClient";
import { courseLevels, currentLevel } from "../../../utils/studentLevels";
import { formatMoney, latestAffiliate, pendingRewards, referralView, tuitionProgress } from "../../../utils/studentFinance";
import { academyPath } from "../AcademyNav";
import ELearningSkeleton from "../ELearningSkeleton";
import LearningErrorNotice from "../LearningErrorNotice";
import useStudentData from "./useStudentData";
import { ProgressBar, StatCard, StatusPill, StudentPage } from "./StudentParts";

/** EH / Student Dashboard — Overview (website document §14). */
export default function StudentOverview() {
  const { t, i18n } = useTranslation("dashboard");
  const data = useStudentData();
  const [user, setUser] = useState(null);
  useEffect(() => {
    let active = true;
    apiFetch(getApiUrl("/auth/user_status"), { cache: "no-store" }).then(response => response.ok ? response.json() : null).then(value => { if (active) setUser(value?.user || null); }).catch(() => {});
    return () => { active = false; };
  }, []);
  if (data.loading) return <ELearningSkeleton label={t("elearning.loading")} direction={i18n.dir()} />;
  if (data.error) return <LearningErrorNotice as="p">{t("elearning.player.loadError")} <button onClick={data.retry}>{t("elearning.retry")}</button></LearningErrorNotice>;
  // Affiliates who did not buy the course use the affiliate dashboard (document §20).
  const affiliate = latestAffiliate(data.programmes);
  if (!data.enrolled && affiliate && affiliate.status !== "not_approved") return <Navigate to="/my-learning/affiliate" replace />;
  const academy = data.learning?.academy, institution = academy?.institution;
  const levels = courseLevels(data.course), level = currentLevel(levels);
  const completed = levels.filter(item => item.state === "completed").length;
  const wallet = data.programmes?.wallet, referrals = data.referrals;
  const progress = Math.round(Number(data.enrolled?.progress?.progress_percent) || 0);
  const { sales, threshold } = tuitionProgress(wallet || data.programmes?.eligibility);
  const applications = data.programmes?.applications || [];
  const money = value => formatMoney(value, wallet?.currency || referrals?.currency, i18n.language);
  return <StudentPage title={user?.first_name ? t("elearning.student.welcomeName", { name: user.first_name }) : t("elearning.student.welcome")}>
    {institution?.member && <div className="institution-welcome" role="status">
      {/* Website document §8, word for word. */}
      <strong>{t("elearning.student.pauWelcomeTitle")}</strong>
      <p>{t("elearning.student.pauWelcomeBody")}</p>
      {institution.label && <StatusPill status="eligible">{institution.label}</StatusPill>}
    </div>}
    <div className="stat-grid">
      <StatCard icon={GraduationCap} label={t("elearning.student.courseAccess")} value={data.enrolled ? t("elearning.student.accessActive") : t("elearning.student.accessNone")}
        detail={data.enrolled?.course?.name} to={data.enrolled ? "/my-learning/course" : academy ? `${academyPath(academy)}/courses` : undefined} />
      <StatCard icon={Layers} label={t("elearning.student.currentLevel")} value={level ? t("elearning.student.levelOf", { number: level.number, total: levels.length || 10 }) : "—"} detail={level?.cefr} to="/my-learning/course" />
      <StatCard icon={BookOpen} label={t("elearning.student.completedLevels")} value={`${completed} / ${levels.length || 10}`} />
      <StatCard icon={TrendingUp} label={t("elearning.student.overallProgress")} value={`${progress}%`}><ProgressBar value={progress} label={t("elearning.student.overallProgress")} /></StatCard>
      <StatCard icon={Share2} label={t("elearning.student.referralSales")} value={String(sales)} detail={referralView(referrals) === "link" ? t("elearning.student.referralActive") : t("elearning.student.referralAfterPurchase")} to="/my-learning/referral" />
      <StatCard icon={ClipboardList} label={t("elearning.student.tuitionProgress")} value={`${Math.min(sales, threshold)} / ${threshold}`} to="/my-learning/applications">
        <ProgressBar value={Math.min(sales, threshold)} max={threshold} label={t("elearning.student.tuitionProgress")} />
      </StatCard>
      <StatCard icon={Wallet} label={t("elearning.student.pendingRewards")} value={referrals?.available ? money(pendingRewards(referrals)) : "—"} />
      <StatCard icon={Wallet} label={t("elearning.student.availableRewards")} value={money(wallet?.available)} detail={t("elearning.student.walletBalance")} to="/my-learning/wallet" />
      <StatCard icon={ClipboardList} label={t("elearning.student.applications")} value={String(applications.length)} detail={applications[0] ? t(`elearning.programmes.${applications[0].status}`) : undefined} to="/my-learning/applications" />
      <StatCard icon={Bell} label={t("elearning.student.notifications")} value={t("elearning.student.viewNotifications")} to="/my-learning/notifications" />
    </div>
    {data.enrolled && <Link className="ecommerce-primary-button student-continue" to={data.course?.continue_lesson_id ? `/my-learning/courses/${data.enrolled.course.id}/lessons/${data.course.continue_lesson_id}` : `/my-learning/courses/${data.enrolled.course.id}`}>{t("elearning.player.continue")}</Link>}
  </StudentPage>;
}
