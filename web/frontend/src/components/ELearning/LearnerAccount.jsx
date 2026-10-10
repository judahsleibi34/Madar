import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowUpRight, BookOpen, Check, Copy, KeyRound, Share2, Target, Trophy, UserRound } from "lucide-react";
import { fetchMyLearning, fetchReferralAccount } from "../../services/elearningPlayer";
import { apiFetch, getApiUrl } from "../../utils/apiClient";
import { academyPath } from "./AcademyNav";
import ELearningSkeleton from "./ELearningSkeleton";

async function loadAccount() {
  const profileRequest = apiFetch(getApiUrl("/auth/user_status"), { cache: "no-store" })
    .then(response => response.ok ? response.json() : null).catch(() => null);
  const referralRequest = fetchReferralAccount().catch(() => ({ error: true, balances: [], history: [] }));
  const first = await fetchMyLearning();
  const courses = [...first.courses];
  let more = first.has_more;
  while (more) {
    const next = await fetchMyLearning(courses.length);
    if (!next.courses.length) throw new Error("Incomplete course list");
    courses.push(...next.courses);
    more = next.has_more;
  }
  return { ...first, courses, user: (await profileRequest)?.user, referrals: await referralRequest };
}

export default function LearnerAccount() {
  const { t, i18n } = useTranslation("dashboard");
  const [state, setState] = useState({ loading: true });
  const [attempt, setAttempt] = useState(0);
  const [copyState, setCopyState] = useState("");
  useEffect(() => {
    let active = true;
    loadAccount().then(data => { if (active) setState({ data }); }).catch(() => { if (active) setState({ error: true }); });
    return () => { active = false; };
  }, [attempt]);
  if (state.loading) return <ELearningSkeleton label={t("elearning.player.loading")} direction={i18n.dir()} />;
  if (state.error) return <section className="learner-account-panel" role="alert"><p>{t("elearning.player.loadError")}</p><button className="ecommerce-secondary-button" onClick={() => { setState({ loading: true }); setAttempt(value => value + 1); }}>{t("elearning.retry")}</button></section>;
  const { courses, user, academy, referrals } = state.data;
  const name = [user?.first_name, user?.last_name].filter(Boolean).join(" ");
  const completed = courses.reduce((sum, item) => sum + item.progress.completed_lessons, 0);
  const total = courses.reduce((sum, item) => sum + item.progress.total_lessons, 0);
  const percent = total ? Math.round(completed / total * 100) : 0;
  const finished = courses.filter(item => item.progress.completion ? item.progress.completion.completed : item.progress.progress_status === "completed").length;
  const invitationUrl = academy?.subdomain ? new URL(academyPath(academy), window.location.origin) : null;
  if (invitationUrl && referrals.enabled && referrals.code) invitationUrl.searchParams.set("ref", referrals.code);
  const invitation = invitationUrl?.href || "";
  const money = (amount, currency) => new Intl.NumberFormat(i18n.language, { style: "currency", currency }).format(Number(amount));
  async function copyLink() {
    try { await navigator.clipboard.writeText(invitation); setCopyState("copied"); }
    catch { setCopyState("copyHelp"); }
  }
  return <div className="learner-account">
    <header className="learner-account-profile learner-account-panel">
      <span className="learner-account-avatar" aria-hidden="true">{name ? name.split(" ").map(part => part[0]).slice(0, 2).join("") : <UserRound size={30} />}</span>
      <div><p className="learner-account-eyebrow">{t("elearning.learner.account")}</p><h1>{name || t("elearning.accountPage.yourProfile")}</h1>{user?.email && <p className="learner-account-email">{user.email}</p>}<p>{t("elearning.accountPage.intro")}</p></div>
      <Link className="ecommerce-secondary-button" to="/my-learning/account/password"><KeyRound size={17} aria-hidden="true" />{t("elearning.learner.changePassword")}</Link>
    </header>
    <div className="learner-account-stats">
      {[ [BookOpen, courses.length, "courses"], [Check, finished, "completedCourses"], [Target, `${percent}%`, "overallProgress"], [Trophy, completed * 10, "myScore"] ].map(([Icon, value, label]) => <section key={label} className="learner-account-stat learner-account-panel"><Icon size={22} aria-hidden="true" /><span>{t(`elearning.accountPage.${label}`)}</span><strong>{value}</strong>{label === "myScore" && <small>{t("elearning.accountPage.scoreHelp")}</small>}</section>)}
    </div>
    <div className="learner-account-columns">
      <section className="learner-account-panel learner-account-courses">
        <header><h2>{t("elearning.accountPage.coursesAndProgress")}</h2><Link to="/my-learning">{t("elearning.academy.viewAll")}<ArrowUpRight size={16} aria-hidden="true" /></Link></header>
        <p className="learner-account-summary">{t("elearning.accountPage.lessonsCompleted", { completed, total })}</p>
        {courses.length ? <ul>{courses.map(item => <li key={item.course.id}><BookOpen size={21} aria-hidden="true" /><div><Link to={`/my-learning/courses/${item.course.id}`}>{item.course.name}</Link><div className="learner-account-course-progress"><progress max="100" value={item.progress.progress_percent} aria-label={t("elearning.accountPage.courseProgress", { name: item.course.name })} /><span>{item.progress.progress_percent}%</span></div><small>{t("elearning.accountPage.lessonsCompleted", { completed: item.progress.completed_lessons, total: item.progress.total_lessons })}</small></div><Link className="learner-account-open" to={`/my-learning/courses/${item.course.id}`} aria-label={t("elearning.accountPage.openCourse", { name: item.course.name })}><ArrowUpRight size={19} /></Link></li>)}</ul> : <div className="learner-account-empty"><BookOpen size={30} /><p>{t("elearning.player.empty")}</p><Link className="ecommerce-primary-button" to={academy ? `${academyPath(academy)}/courses` : "/my-learning/catalog"}>{t("elearning.academy.explore")}</Link></div>}
      </section>
      <aside className="learner-account-panel learner-account-referral">
        <span className="learner-account-share-icon"><Share2 size={25} aria-hidden="true" /></span><h2>{t("elearning.accountPage.inviteFriends")}</h2><p>{t(referrals.enabled ? "elearning.referrals.inviteHelp" : "elearning.accountPage.inviteHelp", { reward: referrals.enabled ? money(referrals.reward_amount, referrals.currency) : "" })}</p>
        {invitation ? <><label htmlFor="learner-invitation-link">{t("elearning.accountPage.invitationLink")}</label><input id="learner-invitation-link" value={invitation} readOnly dir="ltr" onFocus={event => event.target.select()} /><button className="ecommerce-primary-button" onClick={copyLink}>{copyState === "copied" ? <Check size={17} /> : <Copy size={17} />}{t(`elearning.accountPage.${copyState === "copied" ? "copied" : "copyLink"}`)}</button><small>{t(referrals.enabled ? "elearning.referrals.linkHelp" : "elearning.accountPage.linkHelp")}</small><p role="status">{copyState === "copyHelp" ? t("elearning.accountPage.copyHelp") : ""}</p></> : <p>{t("elearning.accountPage.inviteUnavailable")}</p>}
      </aside>
    </div>
    <section className="learner-account-panel learner-account-rewards">
      <header><h2>{t("elearning.referrals.rewards")}</h2><p>{t("elearning.referrals.balanceHelp")}</p></header>
      {referrals.error ? <p role="alert">{t("elearning.referrals.loadError")}</p> : !referrals.available ? <p>{t("elearning.referrals.unavailable")}</p> : <>
        <div className="learner-account-reward-balances">{referrals.balances.length ? referrals.balances.map(balance => <div key={`${balance.currency}:${balance.simulated}`}><span>{t(balance.simulated ? "elearning.referrals.demoBalance" : "elearning.referrals.balance")}</span><strong>{money(balance.amount, balance.currency)}</strong></div>) : <p>{t("elearning.referrals.noRewards")}</p>}</div>
        <p>{t("elearning.referrals.counts", { referred: referrals.referred_count, earned: referrals.earned_count })}</p>
        {referrals.history.length > 0 && <ul className="learner-account-referral-history">{referrals.history.map(item => <li key={item.id}><span>{new Date(item.created_at).toLocaleDateString(i18n.language)}</span><strong>{money(item.amount, item.currency)}</strong><span>{t(`elearning.referrals.${item.status}`)}{item.simulated && ` · ${t("elearning.referrals.demo")}`}</span></li>)}</ul>}
      </>}
    </section>
  </div>;
}
