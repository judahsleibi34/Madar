import { learningDescription } from "../../utils/elearningPresentation";
import AcademyBuilderLanding from "./AcademyBuilderLanding";
import madarLearningLanding from "../../content/pageBuilder/madarLearningLanding.json";
import { getPageBuilderThemeVars } from "../PageBuilder/core/PageBuilder.theme";
import { getAcademyAppearance } from "../../services/academyAppearance";
import { AcademyCompositionContext } from "../PageBuilder/blocks/AcademyDataBlock";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Award, BookOpen, ArrowUpRight, Search, SlidersHorizontal, ChevronDown } from "lucide-react";
import { fetchAcademy, academyReturnPath, loginAcademy, registerAcademy } from "../../services/elearningAcademy";
import ELearningLearnerShell from "./ELearningLearnerShell";
import * as commerce from "../../services/elearningCommerce";
import { resolveMediaUrl } from "../../utils/media";
import StorefrontSeo from "../EcommerceStore/StorefrontSeo";
import AcademyNav, { academyPath } from "./AcademyNav";
import ELearningSkeleton from "./ELearningSkeleton";
import ELearningPlayer from "./ELearningPlayer";
import { Checkout, Price } from "./ELearningCatalog";

const AcademyContext = createContext(null);

function useAcademy(identifier) {
  const [state, setState] = useState({ loading: true }), [revision, setRevision] = useState(0);
  const requestKey = `${identifier || ""}:${revision}`;
  useEffect(() => { if (!identifier) return undefined; let active = true; fetchAcademy(identifier).then(data => { if (active) setState({ requestKey, data }); }).catch(error => { if (active) setState({ requestKey, error }); }); return () => { active = false; }; }, [identifier, requestKey]);
  const refresh = useCallback(() => setRevision(v => v + 1), []);
  return { ...(state.requestKey === requestKey ? state : { loading: true }), refresh };
}

export default function ELearningAcademy({ subdomain }) {
  const params = useParams(), identifier = subdomain || params.subdomain;
  const { t, i18n } = useTranslation("dashboard");
  const state = useAcademy(identifier);
  if (state.loading) return <ELearningSkeleton label={t("elearning.player.loading")} direction={i18n.dir()} />;
  if (state.error) return <main className="academy-error" dir={i18n.dir()}><h1>{t("elearning.academy.unavailable")}</h1><p role="alert">{t("elearning.player.loadError")}</p><button onClick={state.refresh}>{t("elearning.retry")}</button></main>;
  return <AcademyContent data={state.data} refresh={state.refresh} />;
}

function AcademyContent({ data, refresh }) {
  if (import.meta.env.DEV && import.meta.env.VITE_MADAR_LOCAL_LANDING_PREVIEW === "true" && data.site.subdomain === "testing") data = { ...data, landing: madarLearningLanding };
  const { t, i18n } = useTranslation("dashboard");
  const site = getAcademyAppearance(data.site, data.landing);
  const base = academyPath(site), location = useLocation();
  useEffect(() => {
    const code = new URLSearchParams(location.search).get("ref");
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(code || "")) {
      try { sessionStorage.setItem(`academy-referral:${site.subdomain}`, code); } catch { /* Signup can also read the URL directly. */ }
    }
  }, [location.search, site.subdomain]);
  const authPage = /\/login\/?$/.test(location.pathname);
  const view = location.pathname.endsWith("/courses") ? "catalog" : /\/login$/.test(location.pathname) ? "checkout" : "landing";
  const presentation = !/^\/(courses|plans|login|dashboard)(\/|$)/.test(location.pathname.slice(base.length));
  const learnerSurface = data.authenticated && !presentation && !/\/login$/.test(location.pathname);
  const publishedHeader = presentation && data.landing && (data.landing.siteChrome ? data.landing.siteChrome.showHeader : true);
  const selected = data.courses.find(c => location.pathname.endsWith(`/courses/${c.id}`));
  const builderTheme = getPageBuilderThemeVars(data.landing?.theme || site.theme);
  const theme = { ...builderTheme, "--academy-accent": builderTheme["--theme-primary"], "--academy-background": builderTheme["--theme-bg"], "--academy-surface": builderTheme["--theme-surface"], "--academy-text": builderTheme["--theme-text"], "--academy-muted": builderTheme["--theme-text-soft"] };
  const Surface = learnerSurface ? ELearningLearnerShell : GuestSurface;
  return <AcademyContext.Provider value={{ data, refresh }}><Surface site={site}><div className={`academy${presentation ? " academy-presentation" : ""}${learnerSurface ? " academy-learner" : ""}${authPage ? " academy-auth" : ""}`} dir={i18n.dir()} lang={i18n.language} style={theme}>
    <StorefrontSeo origin={window.location.origin} storePath={selected ? `${base}/courses/${selected.id}` : base} locale={i18n.language} site={{ ...site, brand: selected ? `${selected.name} | ${site.brand}` : site.brand, description: learningDescription(selected?.description) || site.description }} view={view} publicPage={{ title: selected ? `${selected.name} | ${site.brand}` : `${view === "catalog" ? `${t("elearning.academy.courses")} | ` : ""}${site.brand}`, description: learningDescription(selected?.description) || site.description, path: location.pathname }} />
    {!learnerSurface && !publishedHeader && <AcademyNav site={site} authenticated={data.authenticated} hasPlans={data.plans.length > 0} />}
    <main className="academy-main"><Routes>
      <Route index element={<AcademyPresentation data={data} />} />
      <Route path="dashboard" element={data.authenticated ? <LearnerHome data={data} /> : <Navigate to={`${base}/login?returnTo=${encodeURIComponent(`${base}/dashboard`)}`} replace />} />
      <Route path="courses" element={<Catalog data={data} />} />
      <Route path="courses/:courseId" element={<Details data={data} refresh={refresh} />} />
      <Route path="plans" element={<Plans data={data} refresh={refresh} />} />
      <Route path="login" element={<AcademyLogin data={data} refresh={refresh} />} />
      <Route path="*" element={<AcademyPresentation data={data} />} />
    </Routes></main>
    {!learnerSurface && (!presentation || !data.landing?.siteChrome?.showFooter) && <footer className="academy-footer"><strong>{site.brand}</strong><p>{site.description}</p><Link to={`${base}/courses`}>{t("elearning.academy.explore")}</Link><span>Madar</span></footer>}
  </div></Surface></AcademyContext.Provider>;
}

function AcademyPresentation({ data }) {
  return <AcademyCompositionContext.Provider value={{ data, renderCollection: (heading, courses) => <Collection title={heading} courses={courses} site={data.site} />, renderPlans: plans => <PlanCards data={{ ...data, plans }} preview /> }}><AcademyBuilderLanding schema={data.landing} authenticated={data.authenticated} registration={data.site.academy_registration} basePath={academyPath(data.site)} /></AcademyCompositionContext.Provider>;
}

function GuestSurface({ children }) { return children; }

function LearnerHome({ data }) {
  const { t } = useTranslation("dashboard");
  const continuing = data.continue_courses || [];
  return <>
    <header className="academy-learner-intro"><h1>{t("elearning.academy.home")}</h1><p>{t("elearning.player.intro")}</p><Link className="academy-button" to="/my-learning">{t("elearning.player.myLearning")}</Link></header>
    <Collection title={t("elearning.player.continue")} courses={continuing} site={data.site} />
    <Collection title={t("elearning.academy.explore")} courses={data.courses} site={data.site} link />
  </>;
}

function CourseCard({ course, site }) {
  const { t } = useTranslation("dashboard");
  return <article className="academy-card" data-course-id={course.id}>
    <Link to={course.view_path || `${academyPath(site)}/courses/${course.id}`} className="academy-cover">{course.cover_asset ? <img src={resolveMediaUrl(course.cover_asset)} alt="" loading="lazy" /> : <BookOpen size={44} aria-hidden="true" />}</Link>
    <div className="academy-card-body"><small>{site.course_label}</small><h3><Link to={course.view_path || `${academyPath(site)}/courses/${course.id}`}>{course.name}</Link></h3><p>{learningDescription(course.description)}</p>
      {course.instructors.length > 0 && <small>{course.instructors.map(i => i.name).join(" · ")}</small>}
      <CourseState course={course} />
      {course.certificate_available && <span className="academy-badge"><Award size={15} />{t("elearning.academy.certificateAvailable")}</span>}
      <PrimaryAction course={course} card />
    </div>
  </article>;
}
function CourseState({ course }) {
  const { t } = useTranslation("dashboard");
  return <div className="academy-course-state">
    {course.progress ? <><progress aria-label={t("elearning.academy.progress")} max="100" value={course.progress.progress_percent} /><strong>{course.progress.progress_percent}% {t("elearning.academy.complete")}</strong>{course.progress.completion?.completed && <span>{t("elearning.player.completed")}</span>}</> : course.cta.included_in ? <strong>{t("elearning.commerce.included", { name: course.cta.included_in.name })}</strong> : course.access_type === "free" ? <strong>{t("elearning.academy.free")}</strong> : course.price ? <><small>{t("elearning.academy.from")}</small><Price terms={course.price} /></> : null}
    {course.credential?.status === "active" && <span className="academy-badge"><Award size={15} />{t("elearning.academy.certificateEarned")}</span>}
  </div>;
}
function Collection({ title, courses, site, link = false }) {
  const { t } = useTranslation("dashboard");
  if (!courses.length) return null;
  return <section className="academy-section"><header><h2>{title}</h2>{link && <Link to={`${academyPath(site)}/courses`}>{t("elearning.academy.viewAll")} <ArrowUpRight size={17} /></Link>}</header><div className="academy-grid">{courses.map(c => <CourseCard key={c.id} course={c} site={site} />)}</div></section>;
}
function Catalog({ data }) {
  const { t } = useTranslation("dashboard"); const [query, setQuery] = useState(""), [access, setAccess] = useState("");
  const filtered = data.courses.filter(c => `${c.name} ${learningDescription(c.description)} ${c.instructors.map(i => i.name).join(" ")}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()) && (!access || c.access_type === access));
  return <div className="academy-catalog">
    <header className="academy-catalog-heading"><h1>{t("elearning.academy.courses")}</h1><p>{t("elearning.academy.catalogIntro")}</p></header>
    <div className="academy-catalog-layout">
      <aside className="academy-filters" aria-label={t("elearning.academy.filters")}>
        <h2><SlidersHorizontal size={17} aria-hidden="true" />{t("elearning.academy.filters")}</h2>
        <label>{t("elearning.academy.search")}<span className="academy-search-control"><input type="search" value={query} onChange={e => setQuery(e.target.value)} /><Search size={18} aria-hidden="true" /></span></label>
        <label>{t("elearning.academy.access")}<span className="academy-select-control"><select value={access} onChange={e => setAccess(e.target.value)}><option value="">{t("elearning.academy.all")}</option><option value="free">{t("elearning.academy.free")}</option><option value="paid">{t("elearning.academy.paid")}</option></select><ChevronDown size={17} aria-hidden="true" /></span></label>
      </aside>
      <div className="academy-catalog-results">
        <p className="academy-results-count" role="status">{t("elearning.academy.results", { count: filtered.length })}</p>
        <Collection title={t("elearning.academy.explore")} courses={filtered} site={data.site} />
        {!filtered.length && <p className="academy-catalog-empty">{t("elearning.academy.empty")}</p>}
      </div>
    </div>
  </div>;
}
function PrimaryAction({ course, card = false }) {
  const { data, refresh } = useContext(AcademyContext), { t } = useTranslation("dashboard"), navigate = useNavigate();
  const [busy, setBusy] = useState(false), [error, setError] = useState(null);
  const base = academyPath(data.site), action = course.cta.action;
  async function enroll() {
    if (!data.authenticated) return navigate(`${base}/login?returnTo=${encodeURIComponent(`${base}/courses/${course.id}?resume=enroll`)}`);
    setBusy(true); setError(null);
    try { await commerce.enrollCatalogCourse(course.id); refresh(); navigate(`/my-learning/courses/${course.id}`); } catch (e) { setError(e); } finally { setBusy(false); }
  }
  return <>{action === "continue" ? <Link className="academy-button" to={course.resume}>{t("elearning.player.continue")}</Link> : action === "certificate" ? <Link className="academy-button" to={card ? `${base}/courses/${course.id}` : `/my-learning/certificates/${course.credential.id}`}>{t(card ? "elearning.academy.card_certificate" : "elearning.certificates.viewCertificate")}</Link> : ["enroll", "enroll_free"].includes(action) ? <button className="academy-button" onClick={enroll} disabled={busy}>{t(`elearning.academy.card_${action}`)}</button> : action === "buy" ? card ? <Link className="academy-button" to={`${base}/courses/${course.id}`}>{t("elearning.academy.card_buy")}</Link> : <a className="academy-button" href="#access-options">{t("elearning.academy.viewPlans")}</a> : <button className="academy-button" disabled>{t(`elearning.academy.card_${action}`)}</button>}{error && <p role="alert">{t("elearning.commerce.error")}</p>}</>;
}
function Details({ data, refresh }) {
  const { courseId } = useParams(), { t } = useTranslation("dashboard");
  const course = data.courses.find(c => c.id === courseId), base = academyPath(data.site);
  const location = useLocation(), navigate = useNavigate();
  const [resumeError, setResumeError] = useState(false);
  useEffect(() => {
    if (!data.authenticated || new URLSearchParams(location.search).get("resume") !== "enroll") return undefined;
    let active = true;
    commerce.enrollCatalogCourse(courseId).then(() => { if (active) { refresh(); navigate(`/my-learning/courses/${courseId}`, { replace: true }); } }).catch(() => { if (active) setResumeError(true); });
    return () => { active = false; };
  }, [courseId, data.authenticated, location.search, navigate, refresh]);
  if (!course) return <p role="alert">{t("elearning.academy.unavailable")}</p>;
  return <>{resumeError && <p role="alert">{t("elearning.commerce.error")}</p>}<nav><Link to={`${base}/courses`}>{t("elearning.academy.courses")}</Link> / {course.name}</nav><section className="academy-detail"><div className="academy-detail-cover">{course.cover_asset ? <img src={resolveMediaUrl(course.cover_asset)} alt="" /> : <BookOpen size={100} />}</div><div><small>{data.site.course_label}</small><h1>{course.name}</h1><p>{learningDescription(course.description)}</p><CourseState course={course} />
    {course.instructors.length > 0 && <p>{data.site.instructor_label}: {course.instructors.map(i => i.name).join(" · ")}</p>}
    <PrimaryAction course={course} />
    {course.certificate_available && <p><Award size={17} /> {t("elearning.academy.certificateAvailable")}</p>}
  </div></section><section className="academy-section"><h2>{t("elearning.player.outline")}</h2><p>{course.outline.length} {data.site.section_label} · {course.outline.reduce((sum, s) => sum + s.lesson_count, 0)} {data.site.lesson_label}</p><ol className="academy-outline">{course.outline.map((s, i) => <li key={i}><strong>{s.name}</strong><span>{s.lesson_count} {data.site.lesson_label}</span></li>)}</ol></section>
    {course.plans.length > 0 && <section className="academy-section" id="access-options"><h2>{t("elearning.academy.chooseAccess")}</h2><Plans data={{ ...data, plans: course.plans }} refresh={refresh} course={course} /></section>}
  </>;
}
function PlanCards({ data, preview = false, buy, busy }) {
  const { t } = useTranslation("dashboard");
  return <div className="academy-grid">{data.plans.slice(0, preview ? 3 : undefined).map(plan => <article className="academy-plan" key={plan.id}><span className="academy-eyebrow">{t(`elearning.commerce.${plan.access_scope}`, { courses: data.site.course_label, course: data.site.course_label })}</span><h3>{plan.name}</h3><Price terms={plan} /><p>{plan.description}</p>{preview ? <Link className="academy-button" to={`${academyPath(data.site)}/plans`}>{t("elearning.academy.viewPlans")}</Link> : <button className="academy-button" disabled={busy} onClick={() => buy(plan)}>{t(plan.billing_type === "one_time" ? "elearning.commerce.buy" : "elearning.academy.subscribe")}</button>}</article>)}</div>;
}
function Plans({ data, refresh, course }) {
  const { t } = useTranslation("dashboard"), navigate = useNavigate(), location = useLocation(); const [checkout, setCheckout] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState(null), [local, setLocal] = useState(false);
  async function buy(plan) {
    const base = academyPath(data.site);
    if (!data.authenticated) return navigate(`${base}/login?returnTo=${encodeURIComponent(`${course ? `${base}/courses/${course.id}` : `${base}/plans`}?resume=checkout&plan=${encodeURIComponent(plan.id)}`)}`);
    setBusy(true); setError(null);
    try { const account = await commerce.fetchMyPlans(); setLocal(account.local_adapter); if (!account.local_adapter) { setError({ unavailable: true }); return; } const result = await commerce.createCheckout(plan.id, course?.id, crypto.randomUUID()); setCheckout(result.checkout); }
    catch (e) { setError(e); } finally { setBusy(false); }
  }
  useEffect(() => {
    const query = new URLSearchParams(location.search);
    if (!data.authenticated || query.get("resume") !== "checkout") return;
    const plan = data.plans.find(item => item.id === query.get("plan"));
    navigate(location.pathname, { replace: true });
    if (plan) queueMicrotask(() => { void buy(plan); });
    // buy reads the current authoritative projection; this effect consumes only the URL intent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.authenticated, location.search]);
  return <>{!course && <h1>{t("elearning.academy.chooseAccess")}</h1>}{error && <p role="alert">{t(error.unavailable ? "elearning.commerce.providerUnavailable" : "elearning.commerce.error")}</p>}{checkout ? <Checkout checkout={checkout} local={local} onClose={() => setCheckout(null)} onChange={() => { setCheckout(null); refresh(); if (course) navigate(`/my-learning/courses/${course.id}`); else navigate("/my-learning/plans"); }} /> : data.plans.length ? <PlanCards data={data} buy={buy} busy={busy} /> : <p>{t("elearning.academy.noPlans")}</p>}</>;
}
function AcademyLogin({ data }) {
  const { t } = useTranslation("dashboard"), location = useLocation();
  const [email, setEmail] = useState(""), [password, setPassword] = useState(""), [name, setName] = useState(""), [registering, setRegistering] = useState(new URLSearchParams(location.search).get("register") === "1" && ["open", "email_domain"].includes(data.site.academy_registration)), [verification, setVerification] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(null);
  const base = academyPath(data.site), requested = new URLSearchParams(location.search).get("returnTo");
  const safeTarget = academyReturnPath(requested, base, window.location.origin, true);
  const target = safeTarget === base || safeTarget.split(/[?#]/)[0] === `${base}/login` ? `${base}/dashboard` : safeTarget;
  async function submit(e) {
    e.preventDefault(); setBusy(true); setError(null);
    try {
      const payload = { email, password, return_to: target };
      if (registering) {
        let referralCode = new URLSearchParams(location.search).get("ref");
        try { referralCode ||= sessionStorage.getItem(`academy-referral:${data.site.subdomain}`); } catch { /* Storage is optional. */ }
        const result = await registerAcademy(data.site.subdomain, { ...payload, full_name: name, ...(referralCode ? { referral_code: referralCode } : {}) });
        try { sessionStorage.removeItem(`academy-referral:${data.site.subdomain}`); } catch { /* Storage is optional. */ }
        if (result.requires_email_verification) { setVerification(true); setRegistering(false); }
        else { const session = await loginAcademy(data.site.subdomain, payload); window.location.assign(session.return_to); }
      }
      else { const result = await loginAcademy(data.site.subdomain, payload); window.location.assign(result.return_to); }
    } catch (failure) { setError(failure); } finally { setBusy(false); }
  }
  if (data.authenticated) return <Navigate to={target} replace />;
  return <form className="academy-login" onSubmit={submit}><h1>{t(registering ? "elearning.learner.createAccount" : "elearning.academy.signIn")}</h1>
    {verification && <p role="status">{t("elearning.learner.verifyEmail")}</p>}
    {registering && <label>{t("elearning.learner.name")}<input autoComplete="name" required value={name} onChange={e => setName(e.target.value)} /></label>}
    <label>{t("elearning.academy.email")}<input type="email" autoComplete="username" required value={email} onChange={e => setEmail(e.target.value)} /></label>
    <label>{t("elearning.academy.password")}<input type="password" minLength={registering ? 8 : undefined} autoComplete={registering ? "new-password" : "current-password"} required value={password} onChange={e => setPassword(e.target.value)} /></label>
    {error && <p role="alert">{t(error.code === "academy_email_domain_not_allowed" ? "elearning.learner.emailDomainDenied" : "elearning.academy.loginError")}</p>}<button className="academy-button" disabled={busy}>{t(registering ? "elearning.learner.createAccount" : "elearning.academy.signIn")}</button>
    {["open", "email_domain"].includes(data.site.academy_registration) && <button type="button" disabled={busy} onClick={() => setRegistering(!registering)}>{t(registering ? "elearning.academy.signIn" : "elearning.learner.createAccount")}</button>}
    <Link to={base}>{t("elearning.academy.home")}</Link>
  </form>;
}
export function HostedAcademyLearning({ subdomain }) {
  const state = useAcademy(subdomain);
  const location = useLocation();
  const { t, i18n } = useTranslation("dashboard");
  if (state.loading) return <ELearningSkeleton label={t("elearning.player.loading")} direction={i18n.dir()} />;
  if (state.error) return <p role="alert">{t("elearning.academy.unavailable")}</p>;
  if (!state.data.authenticated) return <Navigate to={`/academy/login?returnTo=${encodeURIComponent(academyReturnPath(location.pathname + location.search, "/academy", window.location.origin, true))}`} replace />;
  return <ELearningPlayer />;
}

export function AcademyBuilderPreviewProvider({ identifier, children }) {
  const state = useAcademy(identifier);
  if (!identifier) return children;
  if (!state.data) return <AcademyCompositionContext.Provider value={{ loading: state.loading, error: state.error, refresh: state.refresh }}>{children}</AcademyCompositionContext.Provider>;
  const data = state.data;
  return <AcademyContext.Provider value={{ data, refresh: state.refresh }}><AcademyCompositionContext.Provider value={{ data, renderCollection: (heading, courses) => <Collection title={heading} courses={courses} site={data.site} />, renderPlans: plans => <PlanCards data={{ ...data, plans }} preview /> }}>{children}</AcademyCompositionContext.Provider></AcademyContext.Provider>;
}
