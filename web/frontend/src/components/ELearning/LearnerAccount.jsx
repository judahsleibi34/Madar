import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowUpRight, BookOpen, Check, KeyRound, Target, UserRound } from "lucide-react";
import { fetchMyLearning, fetchReferralAccount } from "../../services/elearningPlayer";
import { apiFetch, getApiUrl } from "../../utils/apiClient";
import { academyPath } from "./AcademyNav";
import ReferralInvitation from "./ReferralInvitation";
import { request as programmeRequest } from "./academyProgrammeApi";
import ELearningSkeleton from "./ELearningSkeleton";

async function loadAccount(view, site) {
  const profileRequest = apiFetch(getApiUrl("/auth/user_status"), { cache: "no-store" })
    .then(response => response.ok ? response.json() : null).catch(() => null);
  const referralRequest = view === "profile" ? Promise.resolve({ balances: [], history: [] }) : fetchReferralAccount().catch(() => ({ error: true, balances: [], history: [] }));
  const first = view === "profile" ? await fetchMyLearning() : { courses: [], academy: site };
  const courses = [...first.courses];
  let more = first.has_more;
  while (more && view === "profile") {
    const next = await fetchMyLearning(courses.length);
    if (!next.courses.length) throw new Error("Incomplete course list");
    courses.push(...next.courses);
    more = next.has_more;
  }
  const programme = view === "wallet" ? await programmeRequest("/account").catch(() => null) : null;
  return { ...first, courses, programme, user: (await profileRequest)?.user, referrals: await referralRequest };
}

export default function LearnerAccount({ view = "profile", site }) {
  const { t, i18n } = useTranslation("dashboard");
  const [state, setState] = useState({ loading: true });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    loadAccount(view, site).then(data => { if (active) setState({ data }); }).catch(() => { if (active) setState({ error: true }); });
    return () => { active = false; };
  }, [attempt, view, site]);
  if (state.loading) return <ELearningSkeleton label={t("elearning.player.loading")} direction={i18n.dir()} />;
  if (state.error) return <section className="learner-account-panel" role="alert"><p>{t("elearning.player.loadError")}</p><button className="ecommerce-secondary-button" onClick={() => { setState({ loading: true }); setAttempt(value => value + 1); }}>{t("elearning.retry")}</button></section>;
  const { courses, user, academy, referrals, programme } = state.data;
  const name = [user?.first_name, user?.last_name].filter(Boolean).join(" ");
  const completed = courses.reduce((sum, item) => sum + item.progress.completed_lessons, 0);
  const total = courses.reduce((sum, item) => sum + item.progress.total_lessons, 0);
  const percent = total ? Math.round(completed / total * 100) : 0;
  const finished = courses.filter(item => item.progress.completion ? item.progress.completion.completed : item.progress.progress_status === "completed").length;
  const money = (amount, currency) => new Intl.NumberFormat(i18n.language, { style: "currency", currency }).format(Number(amount));
  return <div className="learner-account">{view !== "profile" && <header className="ecommerce-page-header"><h1>{t(view === "referrals" ? "elearning.programmes.referrals" : view === "wallet" ? "elearning.programmes.wallet" : "elearning.referrals.rewards")}</h1></header>}
    {view === "profile" && <><header className="learner-account-profile learner-account-panel">
      <span className="learner-account-avatar" aria-hidden="true">{name ? name.split(" ").map(part => part[0]).slice(0, 2).join("") : <UserRound size={30} />}</span>
      <div><p className="learner-account-eyebrow">{t("elearning.learner.account")}</p><h1>{name || t("elearning.accountPage.yourProfile")}</h1>{user?.email && <p className="learner-account-email">{user.email}</p>}<p>{t("elearning.accountPage.intro")}</p></div>
      <Link className="ecommerce-secondary-button" to="/my-learning/account/password"><KeyRound size={17} aria-hidden="true" />{t("elearning.learner.changePassword")}</Link>
    </header>
    <div className="learner-account-stats">
      {[ [BookOpen, courses.length, "courses"], [Check, finished, "completedCourses"], [Target, `${percent}%`, "overallProgress"], [Check, completed, "completedLessons"] ].map(([Icon, value, label]) => <section key={label} className="learner-account-stat learner-account-panel"><Icon size={22} aria-hidden="true" /><span>{t(`elearning.accountPage.${label}`)}</span><strong>{value}</strong></section>)}
    </div>
    <div className="learner-account-profile-courses">
      <section className="learner-account-panel learner-account-courses">
        <header><h2>{t("elearning.accountPage.coursesAndProgress")}</h2><Link to="/my-learning">{t("elearning.academy.viewAll")}<ArrowUpRight size={16} aria-hidden="true" /></Link></header>
        <p className="learner-account-summary">{t("elearning.accountPage.lessonsCompleted", { completed, total })}</p>
        {courses.length ? <ul>{courses.map(item => <li key={item.course.id}><BookOpen size={21} aria-hidden="true" /><div><Link to={`/my-learning/courses/${item.course.id}`}>{item.course.name}</Link><div className="learner-account-course-progress"><progress max="100" value={item.progress.progress_percent} aria-label={t("elearning.accountPage.courseProgress", { name: item.course.name })} /><span>{item.progress.progress_percent}%</span></div><small>{t("elearning.accountPage.lessonsCompleted", { completed: item.progress.completed_lessons, total: item.progress.total_lessons })}</small></div><Link className="learner-account-open" to={`/my-learning/courses/${item.course.id}`} aria-label={t("elearning.accountPage.openCourse", { name: item.course.name })}><ArrowUpRight size={19} /></Link></li>)}</ul> : <div className="learner-account-empty"><BookOpen size={30} /><p>{t("elearning.player.empty")}</p><Link className="ecommerce-primary-button" to={academy ? `${academyPath(academy)}/courses` : "/my-learning/catalog"}>{t("elearning.academy.explore")}</Link></div>}
      </section>
    </div></>}
    {view === "referrals" && <ReferralInvitation referrals={referrals} academy={academy} />}
    {["referrals", "rewards", "wallet"].includes(view) && <section className="learner-account-panel learner-account-rewards">
      <header><h2>{t(view === "referrals" ? "elearning.programmes.history" : view === "wallet" ? "elearning.programmes.wallet" : "elearning.referrals.rewards")}</h2>{view === "rewards" && <p>{t("elearning.referrals.balanceHelp")}</p>}</header>
      {referrals.error ? <p role="alert">{t("elearning.referrals.loadError")}</p> : !referrals.available ? <p>{t("elearning.referrals.unavailable")}</p> : <>
        {view !== "referrals" && <div className="learner-account-reward-balances">{view === "wallet" && referrals.wallet ? <><div><span>{t("elearning.programmes.available")}</span><strong>{money(referrals.wallet.available, referrals.wallet.currency)}</strong>{programme?.capabilities?.withdrawal && programme.settings?.withdrawals_enabled && <Link to="/my-learning/withdrawals">{t("elearning.programmes.withdrawal")}</Link>}</div>{["pending", "total_earned", "total_withdrawn", "debt"].map(key => <div key={key}><span>{t(key === "pending" ? "elearning.affiliate.reserved" : `elearning.programmes.${key}`)}</span><strong>{money(referrals.wallet[key], referrals.wallet.currency)}</strong></div>)}</> : referrals.balances.length ? referrals.balances.map(balance => <div key={`${balance.currency}:${balance.simulated}`}><span>{t(balance.simulated ? "elearning.referrals.demoBalance" : "elearning.referrals.balance")}</span><strong>{money(balance.amount, balance.currency)}</strong></div>) : <p>{t("elearning.referrals.noRewards")}</p>}</div>}
        {view !== "wallet" && <p>{t("elearning.referrals.counts", { referred: referrals.referred_count, earned: referrals.earned_count })}</p>}
        {view !== "wallet" && <div className="affiliate-table-scroll"><table><caption>{t(view === "rewards" ? "elearning.referrals.rewards" : "elearning.programmes.referrals")}</caption><thead><tr>{["date", "amount", "statusColumn"].map(key => <th scope="col" key={key}>{t(`elearning.affiliate.${key}`)}</th>)}</tr></thead><tbody>{(referrals.history || []).filter(item => view !== "rewards" || ["earned", "reversed"].includes(item.status)).map(item => <tr key={item.id}><td>{new Date(view === "rewards" ? item.reversed_at || item.earned_at || item.created_at : item.created_at).toLocaleDateString(i18n.language)}</td><td>{money(item.amount, item.currency)}{item.simulated && ` · ${t("elearning.referrals.demo")}`}</td><td>{t(`elearning.referrals.${item.status}`)}</td></tr>)}</tbody></table></div>}
      </>}
    </section>}
  </div>;
}
