import { createPortal } from "react-dom";
import EcommerceToast from "../DashboardBuilder/EcommerceToast";
import LearningErrorNotice from "./LearningErrorNotice";
import { localizePresentation } from "../PageBuilder/core/PageBuilder.presentationLocalization";
import { learningDescription } from "../../utils/elearningPresentation";
import AcademyBuilderLanding from "./AcademyBuilderLanding";
import useAcademySiteChrome from "./useAcademySiteChrome";
import { getLiveArtboardViewportMode } from "../PageBuilder/core/PageBuilder.artboard";
import { resolveStrictPublishedPageByPath, getPublicPagePath } from "../PageBuilder/core/PageBuilder.routing";
import { getPageBuilderThemeVars } from "../PageBuilder/core/PageBuilder.theme";
import { getAcademyAppearance } from "../../services/academyAppearance";
import { AcademyCompositionContext } from "../PageBuilder/blocks/AcademyDataBlock";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Award, BookOpen, ArrowUpRight, Search, SlidersHorizontal, ChevronDown, Eye, EyeOff } from "lucide-react";
import { fetchAcademy, academyReturnPath, loginAcademy, registerAcademy, recordReferralClick } from "../../services/elearningAcademy";
import ELearningLearnerShell from "./ELearningLearnerShell";
import * as commerce from "../../services/elearningCommerce";
import { resolveMediaUrl } from "../../utils/media";
import StorefrontSeo from "../EcommerceStore/StorefrontSeo";
import AcademyNav, { academyPath } from "./AcademyNav";
import ELearningSkeleton from "./ELearningSkeleton";
import ELearningPlayer from "./ELearningPlayer";
import { fetchLearningAccountContext } from "../../services/elearningPlayer";
import { Checkout, Price } from "./ELearningCatalog";
import { openCheckout, paymentNotice, paymentsAvailable } from "../../utils/learningPayments";

const AcademyContext = createContext(null);

const fetchAcademyPreview = identifier => fetchAcademy(identifier, null, true);
const fetchHostedLearningContext = async () => { await fetchLearningAccountContext(); return { authenticated: true }; };

function useAcademy(identifier, load = fetchAcademy) {
  const [state, setState] = useState({ loading: true }), [revision, setRevision] = useState(0);
  const requestKey = `${identifier || ""}:${revision}`;
  useEffect(() => { if (!identifier) return undefined; let active = true; load(identifier).then(data => { if (active) setState({ requestKey, data }); }).catch(error => { if (active) setState({ requestKey, error }); }); return () => { active = false; }; }, [identifier, requestKey, load]);
  const refresh = useCallback(() => setRevision(v => v + 1), []);
  return { ...(state.requestKey === requestKey ? state : { loading: true }), refresh };
}

export default function ELearningAcademy({ subdomain }) {
  const params = useParams(), identifier = subdomain || params.subdomain;
  const { t, i18n } = useTranslation("dashboard");
  const state = useAcademy(identifier);
  if (state.loading) return <ELearningSkeleton label={t("elearning.player.loading")} direction={i18n.dir()} />;
  if (state.error) return <main className="academy-error" dir={i18n.dir()}><StorefrontSeo origin={window.location.origin} locale={i18n.language} site={{ brand: t("elearning.academy.unavailable") }} view="missing" /><h1>{t("elearning.academy.unavailable")}</h1><LearningErrorNotice as="p">{t("elearning.player.loadError")}</LearningErrorNotice><button onClick={state.refresh}>{t("elearning.retry")}</button></main>;
  return <AcademyContent data={state.data} refresh={state.refresh} />;
}

function AcademyContent({ data, refresh }) {
  const { t, i18n } = useTranslation("dashboard");
  const site = getAcademyAppearance(data.site, data.landing);
  const base = academyPath(site), location = useLocation();
  useEffect(() => {
    const code = new URLSearchParams(location.search).get("ref");
    if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(code || "")) {
      try {
        const previous = sessionStorage.getItem(`academy-referral:${site.subdomain}`);
        sessionStorage.setItem(`academy-referral:${site.subdomain}`, code);
        if (previous !== code) recordReferralClick(site.subdomain, code).catch(() => {});
      } catch { /* Signup can also read the URL directly. */ }
    }
  }, [location.search, site.subdomain]);
  const relativePath = location.pathname.slice(base.length).replace(/\/+$/, "") || "/";
  const authPage = relativePath === "/login";
  const presentation = !/^\/(courses|plans|login|dashboard)(\/|$)/.test(location.pathname.slice(base.length));
  const learnerSurface = data.authenticated && !presentation && !/\/login$/.test(location.pathname);
  const selected = data.courses.find(c => relativePath === `/courses/${c.id}`);
  const publishedPage = presentation ? resolveStrictPublishedPageByPath(data.landing?.pages, relativePath, data.landing?.defaultPageId) : null;
  const missing = presentation ? !publishedPage : !selected && !["/courses", "/plans", "/login", "/dashboard"].includes(relativePath);
  const view = missing ? "missing" : authPage || relativePath === "/dashboard" ? "checkout" : "landing";
  const localizedPage = publishedPage ? localizePresentation(publishedPage,i18n.language.startsWith("ar") ? "ar" : "en") : null;
  const title = localizedPage?.seo?.title || (selected ? `${selected.name} | ${site.brand}` : relativePath === "/courses" ? `${t("elearning.academy.courses")} | ${site.brand}` : publishedPage?.name && relativePath !== "/" ? `${publishedPage.name} | ${site.brand}` : site.brand);
  const builderTheme = getPageBuilderThemeVars(data.landing?.theme || site.theme);
  const theme = { ...builderTheme, "--academy-accent": builderTheme["--theme-primary"], "--academy-background": builderTheme["--theme-bg"], "--academy-surface": builderTheme["--theme-surface"], "--academy-text": builderTheme["--theme-text"], "--academy-muted": builderTheme["--theme-text-soft"] };
  if (authPage) return <AcademyContext.Provider value={{ data, refresh }}><div className="academy academy-auth" dir={i18n.dir()} lang={i18n.language} style={theme}>
    <StorefrontSeo origin={window.location.origin} storePath={base} locale={i18n.language} site={site} view="checkout" />
    <AcademyAuthSurface data={data} basePath={base}><AcademyLogin data={data} /></AcademyAuthSurface>
  </div></AcademyContext.Provider>;
  const Surface = learnerSurface ? ELearningLearnerShell : GuestSurface;
  return <AcademyContext.Provider value={{ data, refresh }}><Surface site={site}><div className={`academy${presentation ? " academy-presentation" : ""}${learnerSurface ? " academy-learner" : ""}${authPage ? " academy-auth" : ""}`} dir={i18n.dir()} lang={i18n.language} style={theme}>
    <StorefrontSeo origin={window.location.origin} storePath={base} locale={i18n.language} site={site} view={view} publicPage={{ title, description: learningDescription(selected?.description) || localizedPage?.seo?.description || site.description, path: publishedPage ? getPublicPagePath(base, publishedPage) : `${base}${relativePath === "/" ? "" : relativePath}` }} />
    {!learnerSurface && !presentation && <AcademyNav site={site} authenticated={data.authenticated} hasPlans={data.plans.length > 0} chrome={data.landing?.academyChrome} />}
    <main className="academy-main"><Routes>
      <Route index element={<AcademyPresentation data={data} />} />
      <Route path="dashboard" element={data.authenticated ? <LearnerHome data={data} /> : <Navigate to={`${base}/login?returnTo=${encodeURIComponent(`${base}/dashboard`)}`} replace />} />
      <Route path="courses" element={<Catalog data={data} />} />
      <Route path="courses/:courseId" element={<Details data={data} refresh={refresh} />} />
      <Route path="plans" element={<Plans data={data} refresh={refresh} />} />
      <Route path="login" element={<AcademyLogin data={data} refresh={refresh} />} />
      <Route path="*" element={<AcademyPresentation data={data} />} />
    </Routes></main>
    {!learnerSurface && !presentation && <footer className="academy-footer"><strong>{site.brand}</strong><p>{site.description}</p><Link to={`${base}/courses`}>{t("elearning.academy.explore")}</Link><span>Madar</span></footer>}
  </div></Surface></AcademyContext.Provider>;
}

function AcademyPresentation({ data }) {
  return <AcademyCompositionContext.Provider value={{ data, renderCollection: (heading, courses) => <Collection title={heading} courses={courses} site={data.site} />, renderPlans: plans => <PlanCards data={{ ...data, plans }} preview /> }}><AcademyBuilderLanding schema={data.landing} authenticated={data.authenticated} registration={data.site.academy_registration} basePath={academyPath(data.site)} /></AcademyCompositionContext.Provider>;
}

function AcademyAuthSurface({ data, basePath, children }) {
  const { i18n } = useTranslation("dashboard");
  const [width, setWidth] = useState(window.innerWidth);
  useEffect(() => { const resize = () => setWidth(window.innerWidth); window.addEventListener("resize", resize); return () => window.removeEventListener("resize", resize); }, []);
  const schema = localizePresentation(data.landing, i18n.language.startsWith("ar") ? "ar" : "en");
  const { renderSiteHeader, renderSiteFooter } = useAcademySiteChrome({ schema, basePath, authenticated: data.authenticated, registration: data.site.academy_registration });
  return <div className="academy-landing-region tenant-runtime-page academy-auth-surface"><div className={`builder-canvas viewport-${getLiveArtboardViewportMode(width)}`}>
    {renderSiteHeader()}<main className="academy-main">{children}</main>{renderSiteFooter()}
  </div></div>;
}

function GuestSurface({ children }) { return children; }

function LearnerHome() { return <Navigate to="/my-learning/dashboard" replace />; }

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
// Guests may browse every published course; starting one always goes through academy sign-in first.
function startPath(course, data) {
  const base = academyPath(data.site), resume = `${base}/courses/${course.id}?resume=start`, action = course.cta.action;
  if (!data.authenticated) return `${base}/login?returnTo=${encodeURIComponent(resume)}`;
  if (action === "continue") return course.resume;
  return ["enroll", "enroll_free"].includes(action) ? resume : null;
}
function PrimaryAction({ course, card = false }) {
  const { data, refresh } = useContext(AcademyContext), { t } = useTranslation("dashboard"), navigate = useNavigate();
  const [busy, setBusy] = useState(false), [error, setError] = useState(null);
  const base = academyPath(data.site), action = course.cta.action;
  if (!data.authenticated && card && action === "unavailable") return <Link className="academy-button" to={course.view_path || `${base}/courses/${course.id}`}>{t("elearning.academy.card_buy")}</Link>;
  if (!data.authenticated && action === "unavailable") return <Link className="academy-button" to={startPath(course, data)}>{t("elearning.academy.startCourse")}</Link>;
  async function enroll() {
    if (!data.authenticated) return navigate(`${base}/login?returnTo=${encodeURIComponent(`${base}/courses/${course.id}?resume=enroll`)}`);
    setBusy(true); setError(null);
    try { await commerce.enrollCatalogCourse(course.id); refresh(); navigate(`/my-learning/courses/${course.id}`); } catch (e) { setError(e); } finally { setBusy(false); }
  }
  return <>{action === "continue" ? <Link className="academy-button" to={course.resume}>{t("elearning.player.continue")}</Link> : action === "certificate" ? <Link className="academy-button" to={card ? `${base}/courses/${course.id}` : `/my-learning/certificates/${course.credential.id}`}>{t(card ? "elearning.academy.card_certificate" : "elearning.certificates.viewCertificate")}</Link> : ["enroll", "enroll_free"].includes(action) ? <button className="academy-button" onClick={enroll} disabled={busy}>{t(`elearning.academy.card_${action}`)}</button> : action === "buy" ? card ? <Link className="academy-button" to={`${base}/courses/${course.id}`}>{t("elearning.academy.card_buy")}</Link> : <a className="academy-button" href="#access-options">{t("elearning.academy.viewPlans")}</a> : card ? <button className="academy-button" disabled>{t(`elearning.academy.card_${action}`)}</button> : <div className="academy-access-blocked" role="status"><strong>{t(`elearning.academy.card_${action}`)}</strong><p>{t(action === "suspended" ? "elearning.academy.suspendedHelp" : "elearning.academy.unavailableHelp")}</p></div>}{error && <LearningErrorNotice as="p">{t("elearning.commerce.error")}</LearningErrorNotice>}</>;
}
function Details({ data, refresh }) {
  const { courseId } = useParams(), { t } = useTranslation("dashboard");
  const course = data.courses.find(c => c.id === courseId), base = academyPath(data.site);
  const location = useLocation(), navigate = useNavigate();
  const [resumeError, setResumeError] = useState(false);
  useEffect(() => {
    const resume = new URLSearchParams(location.search).get("resume");
    if (!course || !data.authenticated || !["enroll", "start"].includes(resume)) return undefined;
    if (resume === "start" && course.cta.action === "continue") { navigate(course.resume, { replace: true }); return undefined; }
    if (resume === "start" && !["enroll", "enroll_free"].includes(course.cta.action)) { navigate(location.pathname, { replace: true }); return undefined; }
    let active = true;
    commerce.enrollCatalogCourse(courseId).then(() => { if (active) { refresh(); navigate(`/my-learning/courses/${courseId}`, { replace: true }); } }).catch(() => { if (active) setResumeError(true); });
    return () => { active = false; };
  }, [course, courseId, data.authenticated, location.pathname, location.search, navigate, refresh]);
  if (!course) return <LearningErrorNotice as="p">{t("elearning.academy.unavailable")}</LearningErrorNotice>;
  return <>{resumeError && <LearningErrorNotice as="p">{t("elearning.commerce.error")}</LearningErrorNotice>}<nav><Link to={`${base}/courses`}>{t("elearning.academy.courses")}</Link> / {course.name}</nav><section className="academy-detail"><div className="academy-detail-cover">{course.cover_asset ? <img src={resolveMediaUrl(course.cover_asset)} alt="" /> : <BookOpen size={100} />}</div><div><small>{data.site.course_label}</small><h1>{course.name}</h1><p>{learningDescription(course.description)}</p><CourseState course={course} />
    {course.instructors.length > 0 && <p>{data.site.instructor_label}: {course.instructors.map(i => i.name).join(" · ")}</p>}
    <PrimaryAction course={course} />
    {course.certificate_available && <p><Award size={17} /> {t("elearning.academy.certificateAvailable")}</p>}
  </div></section><section className="academy-section"><h2>{t("elearning.player.outline")}</h2><p>{course.outline.length} {data.site.section_label} · {course.outline.reduce((sum, s) => sum + s.lesson_count, 0)} {data.site.lesson_label}</p><CourseOutline course={course} data={data} /></section>
    {course.plans.length > 0 && <section className="academy-section" id="access-options"><h2>{t("elearning.academy.chooseAccess")}</h2><Plans data={{ ...data, plans: course.plans }} refresh={refresh} course={course} /></section>}
  </>;
}
function CourseOutline({ course, data }) {
  const start = startPath(course, data);
  return <ol className="academy-outline">{course.outline.map((s, i) => <li key={i}>{s.topics?.length ? <details>
    <summary><strong>{s.name}</strong><span>{s.lesson_count} {data.site.lesson_label}</span><ChevronDown size={17} aria-hidden="true" /></summary>
    <ol className="academy-outline-topics">{s.topics.map((topic, j) => <li key={j}>{start ? <Link to={start}>{topic}</Link> : <span>{topic}</span>}</li>)}</ol>
  </details> : <div className="academy-outline-row"><strong>{s.name}</strong><span>{s.lesson_count} {data.site.lesson_label}</span></div>}</li>)}</ol>;
}
function PlanCards({ data, preview = false, buy, busy, available = false }) {
  const { t } = useTranslation("dashboard");
  return <div className="academy-grid">{data.plans.slice(0, preview ? 3 : undefined).map(plan => <article className="academy-plan" key={plan.id}><span className="academy-eyebrow">{t(`elearning.commerce.${plan.access_scope}`, { courses: data.site.course_label, course: data.site.course_label })}</span><h3>{plan.name}</h3><Price terms={plan} /><p>{plan.description}</p>{preview ? <Link className="academy-button" to={`${academyPath(data.site)}/plans`}>{t("elearning.academy.viewPlans")}</Link> : <button className="academy-button" disabled={busy || (data.authenticated && !available)} onClick={() => buy(plan)}>{t(!data.authenticated ? "elearning.learner.logIn" : plan.billing_type === "one_time" ? "elearning.commerce.buy" : "elearning.academy.subscribe")}</button>}</article>)}</div>;
}
function Plans({ data, refresh, course }) {
  const { t } = useTranslation("dashboard"), navigate = useNavigate(), location = useLocation(); const [checkout, setCheckout] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState(null), [local, setLocal] = useState(false), [availability, setAvailability] = useState("loading"), [availabilityRevision, setAvailabilityRevision] = useState(0), [notice, setNotice] = useState("elearning.commerce.localOnly");
  useEffect(() => {
    if (!data.authenticated) return undefined;
    let active = true;
    commerce.fetchMyPlans().then(account => { if (active) { setLocal(Boolean(account.local_adapter)); setNotice(paymentNotice(account)); setAvailability(paymentsAvailable(account) ? "available" : "unavailable"); } }).catch(() => { if (active) setAvailability("error"); });
    return () => { active = false; };
  }, [data.authenticated, availabilityRevision]);
  async function buy(plan) {
    const base = academyPath(data.site);
    if (!data.authenticated) return navigate(`${base}/login?returnTo=${encodeURIComponent(`${course ? `${base}/courses/${course.id}` : `${base}/plans`}?resume=checkout&plan=${encodeURIComponent(plan.id)}`)}`);
    setBusy(true); setError(null);
    try { const account = await commerce.fetchMyPlans(); setLocal(account.local_adapter); if (!paymentsAvailable(account)) { setError({ unavailable: true }); return; } openCheckout(await commerce.createCheckout(plan.id, course?.id, crypto.randomUUID()), setCheckout); }
    catch (e) { setError(e); } finally { setBusy(false); }
  }
  useEffect(() => {
    const query = new URLSearchParams(location.search);
    if (!data.authenticated || availability === "loading" || query.get("resume") !== "checkout") return;
    const plan = data.plans.find(item => item.id === query.get("plan"));
    navigate(location.pathname, { replace: true });
    if (plan && availability === "available") queueMicrotask(() => { void buy(plan); });
    // buy reads the current authoritative projection; this effect consumes only the URL intent.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.authenticated, location.search, availability]);
  return <>{!course && <h1>{t("elearning.academy.chooseAccess")}</h1>}{data.plans.length > 0 && <LearningErrorNotice as="p" role={availability === "error" ? "alert" : "status"}>{t(!data.authenticated || availability === "unavailable" ? "elearning.commerce.providerUnavailable" : availability === "available" ? notice : availability === "error" ? "elearning.commerce.error" : "elearning.loading")}</LearningErrorNotice>}{availability === "error" && <button type="button" onClick={() => { setAvailability("loading"); setAvailabilityRevision(value => value + 1); }}>{t("elearning.retry")}</button>}{error && <LearningErrorNotice as="p">{t(error.unavailable ? "elearning.commerce.providerUnavailable" : "elearning.commerce.error")}</LearningErrorNotice>}{checkout ? <Checkout checkout={checkout} local={local} onClose={() => setCheckout(null)} onChange={() => { setCheckout(null); refresh(); if (course) navigate(`/my-learning/courses/${course.id}`); else navigate("/my-learning/plans"); }} /> : data.plans.length ? <PlanCards data={data} buy={buy} busy={busy || (data.authenticated && availability === "loading")} available={availability === "available"} /> : <p>{t("elearning.academy.noPlans")}</p>}</>;
}
function AcademyLogin({ data }) {
  const { t, i18n } = useTranslation("dashboard"), location = useLocation(), navigate = useNavigate();
  const [email, setEmail] = useState(""), [password, setPassword] = useState(""), [firstName, setFirstName] = useState(""), [lastName, setLastName] = useState(""), [confirmPassword, setConfirmPassword] = useState(""), [fieldErrors, setFieldErrors] = useState({}), [visible, setVisible] = useState({}), [country, setCountry] = useState(""), [university, setUniversity] = useState(""), [termsAccepted, setTermsAccepted] = useState(false), [verification, setVerification] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(null);
  const registering = new URLSearchParams(location.search).get("register") === "1" && ["open", "email_domain"].includes(data.site.academy_registration);
  const switchMode = next => { const query = new URLSearchParams(location.search); if (next) query.set("register", "1"); else query.delete("register"); setPassword(""); setConfirmPassword(""); setError(null); setFieldErrors({}); navigate({ pathname: location.pathname, search: query.toString() }); };
  // Tenant-owned options from the academy's published website (e.g. EduHope).
  const profile = data.landing?.academyRegistration || {}, extraFields = Array.isArray(profile.fields) ? profile.fields : [];
  const legalPath = id => { const page = (data.landing?.pages || []).find(item => item.id === id); return page ? `${academyPath(data.site)}${page.slug === "/" ? "" : page.slug}` : null; };
  const base = academyPath(data.site), requested = new URLSearchParams(location.search).get("returnTo");
  const safeTarget = academyReturnPath(requested, base, window.location.origin, true);
  const target = safeTarget === base || safeTarget.split(/[?#]/)[0] === `${base}/login` ? `${base}/dashboard` : safeTarget;
  async function submit(e) {
    e.preventDefault();
    if (registering) {
      // Same per-field rules and copy as the main Madar sign-up form.
      const required = t("validation.required", { ns: "auth" }), next = {};
      if (!firstName.trim()) next.firstName = required;
      if (!lastName.trim()) next.lastName = required;
      if (!email.trim()) next.email = required; else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) next.email = t("validation.invalidEmail", { ns: "auth" });
      if (!password) next.password = required; else if (password.length < 8) next.password = t("validation.passwordLength", { ns: "auth" });
      if (extraFields.includes("country") && !country.trim()) next.country = required;
      if (profile.requireTerms && !termsAccepted) next.terms = t("elearning.academy.termsRequired");
      if (!confirmPassword) next.confirmPassword = required; else if (password && password !== confirmPassword) next.confirmPassword = t("signup.passwordMismatch", { ns: "auth" });
      setFieldErrors(next);
      if (Object.keys(next).length) return;
    }
    setBusy(true); setError(null);
    try {
      const payload = { email, password, return_to: target };
      if (registering) {
        let referralCode = new URLSearchParams(location.search).get("ref");
        try { referralCode ||= sessionStorage.getItem(`academy-referral:${data.site.subdomain}`); } catch { /* Storage is optional. */ }
        const result = await registerAcademy(data.site.subdomain, { ...payload, full_name: `${firstName.trim()} ${lastName.trim()}`, ...(extraFields.includes("country") ? { country: country.trim() } : {}), ...(extraFields.includes("university") && university.trim() ? { university: university.trim() } : {}), ...(profile.requireTerms ? { terms_accepted: termsAccepted } : {}), ...(referralCode ? { referral_code: referralCode } : {}) });
        try { sessionStorage.removeItem(`academy-referral:${data.site.subdomain}`); } catch { /* Storage is optional. */ }
        if (result.requires_email_verification) { setVerification(true); switchMode(false); }
        else { const session = await loginAcademy(data.site.subdomain, payload); window.location.assign(session.return_to); }
      }
      else { const result = await loginAcademy(data.site.subdomain, payload); window.location.assign(result.return_to); }
    } catch (failure) { setError(failure); } finally { setBusy(false); }
  }
  if (data.authenticated) return <Navigate to={target} replace />;
  const fieldError = key => fieldErrors[key] ? <span className="academy-field-error" id={`academy-${key}-error`} role="alert">{fieldErrors[key]}</span> : null;
  const invalid = key => fieldErrors[key] ? { "aria-invalid": true, "aria-describedby": `academy-${key}-error` } : {};
  const edit = (key, setter) => e => { setter(e.target.value); if (fieldErrors[key]) setFieldErrors(current => ({ ...current, [key]: undefined })); };
  const secret = (key, value, setter, label, toggle) => <label>{label}<span className="academy-password-field"><input type={visible[key] ? "text" : "password"} name={key} placeholder={label} autoComplete="new-password" dir="ltr" value={value} onChange={edit(key, setter)} {...invalid(key)} /><button type="button" aria-label={t(toggle, { ns: "auth" })} onClick={() => setVisible(current => ({ ...current, [key]: !current[key] }))}>{visible[key] ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}</button></span>{fieldError(key)}</label>;
  // Server outcomes are explained once in a toast; field problems stay inline.
  const failure = !error ? null : registering && error.status === 409 ? ["accountExistsTitle", "accountExists"] : error.code === "email_not_verified" ? ["loginErrorTitle", "verifyEmail"] : error.code === "academy_email_domain_not_allowed" ? ["signupErrorTitle", "emailDomainDenied"] : registering ? ["signupErrorTitle", "signupError"] : error.status === 401 ? ["loginErrorTitle", "wrongCredentials"] : error.status === 403 ? ["notMemberTitle", "notMember"] : ["loginErrorTitle", "loginError"];
  const toast = failure && createPortal(<EcommerceToast type="error" dir={i18n.dir()} onDismiss={() => setError(null)} title={t(`elearning.academy.${failure[0]}`)} message={t(failure[1] === "verifyEmail" || failure[1] === "emailDomainDenied" ? `elearning.learner.${failure[1]}` : `elearning.academy.${failure[1]}`)} />, document.body);
  return <>{toast}<form className={`academy-login builder-auth-component${registering ? " academy-register" : ""}`} autoComplete="on" noValidate={registering} onSubmit={submit}><h1>{t(registering ? "elearning.learner.createAccount" : "elearning.academy.signIn")}</h1>
    {verification && <p role="status">{t("elearning.learner.verifyEmail")}</p>}
    {registering ? <>
      <h2 className="academy-auth-section">{t("signup.accountSection", { ns: "auth" })}</h2>
      <div className="academy-register-row">
        <label>{t("signup.firstName", { ns: "auth" })}<input name="firstName" autoComplete="given-name" placeholder={t("signup.firstName", { ns: "auth" })} value={firstName} onChange={edit("firstName", setFirstName)} {...invalid("firstName")} />{fieldError("firstName")}</label>
        <label>{t("signup.lastName", { ns: "auth" })}<input name="lastName" autoComplete="family-name" placeholder={t("signup.lastName", { ns: "auth" })} value={lastName} onChange={edit("lastName", setLastName)} {...invalid("lastName")} />{fieldError("lastName")}</label>
      </div>
      <label>{t("signup.email", { ns: "auth" })}<input type="email" name="email" autoComplete="username" dir="ltr" placeholder={t("signup.email", { ns: "auth" })} value={email} onChange={edit("email", setEmail)} {...invalid("email")} />{fieldError("email")}</label>
      <div className="academy-register-row">
        {secret("password", password, setPassword, t("signup.password", { ns: "auth" }), "signup.togglePassword")}
        {secret("confirmPassword", confirmPassword, setConfirmPassword, t("signup.confirmPassword", { ns: "auth" }), "signup.toggleConfirmPassword")}
      </div>
      {(extraFields.includes("country") || extraFields.includes("university")) && <div className="academy-register-row">
        {extraFields.includes("country") && <label>{t("elearning.academy.country")}<input name="country" autoComplete="country-name" placeholder={t("elearning.academy.country")} value={country} onChange={edit("country", setCountry)} {...invalid("country")} />{fieldError("country")}</label>}
        {extraFields.includes("university") && <label>{t("elearning.academy.university")}<input name="university" autoComplete="organization" placeholder={t("elearning.academy.university")} value={university} onChange={e => setUniversity(e.target.value)} /></label>}
      </div>}
      {profile.requireTerms && <label className="academy-terms-check"><span><input type="checkbox" name="terms" checked={termsAccepted} onChange={e => { setTermsAccepted(e.target.checked); if (fieldErrors.terms) setFieldErrors(current => ({ ...current, terms: undefined })); }} {...invalid("terms")} /><span>{t("elearning.academy.termsAgreePrefix")} {legalPath(profile.termsPageId) ? <Link to={legalPath(profile.termsPageId)} target="_blank" rel="noopener">{t("elearning.academy.termsLink")}</Link> : t("elearning.academy.termsLink")} {t("elearning.academy.termsAnd")} {legalPath(profile.privacyPageId) ? <Link to={legalPath(profile.privacyPageId)} target="_blank" rel="noopener">{t("elearning.academy.privacyLink")}</Link> : t("elearning.academy.privacyLink")}</span></span>{fieldError("terms")}</label>}
    </> : <>
      <label>{t("elearning.academy.email")}<input type="email" autoComplete="username" required value={email} onChange={e => setEmail(e.target.value)} /></label>
      <label>{t("elearning.academy.password")}<input type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} /></label>
    </>}
    <button className="academy-button" disabled={busy}>{t(registering ? "elearning.learner.createAccount" : "elearning.academy.signIn")}</button>
    {["open", "email_domain"].includes(data.site.academy_registration) && <p className="academy-auth-switch">{t(registering ? "elearning.academy.haveAccount" : "elearning.academy.noAccount")} <button type="button" className="academy-inline-link" disabled={busy} onClick={() => switchMode(!registering)}>{t(registering ? "elearning.academy.signIn" : "elearning.learner.createAccount")}</button></p>}
  </form></>;
}
export function HostedAcademyLearning({ subdomain }) {
  const state = useAcademy(subdomain, fetchHostedLearningContext);
  const location = useLocation();
  const { t, i18n } = useTranslation("dashboard");
  if (state.loading) return <ELearningSkeleton label={t("elearning.player.loading")} direction={i18n.dir()} />;
  if (state.error?.status === 401) return <Navigate to={`/academy/login?returnTo=${encodeURIComponent(academyReturnPath(location.pathname + location.search, "/academy", window.location.origin, true))}`} replace />;
  if (state.error) return <LearningErrorNotice as="p">{t("elearning.academy.unavailable")}</LearningErrorNotice>;
  if (!state.data.authenticated) return <Navigate to={`/academy/login?returnTo=${encodeURIComponent(academyReturnPath(location.pathname + location.search, "/academy", window.location.origin, true))}`} replace />;
  return <ELearningPlayer />;
}

export function AcademyBuilderPreviewProvider({ identifier, children }) {
  const state = useAcademy(identifier, fetchAcademyPreview);
  if (!identifier) return children;
  if (!state.data) return <AcademyCompositionContext.Provider value={{ loading: state.loading, error: state.error, refresh: state.refresh }}>{children}</AcademyCompositionContext.Provider>;
  const data = state.data;
  return <AcademyContext.Provider value={{ data, refresh: state.refresh }}><AcademyCompositionContext.Provider value={{ data, renderCollection: (heading, courses) => <Collection title={heading} courses={courses} site={data.site} />, renderPlans: plans => <PlanCards data={{ ...data, plans }} preview /> }}>{children}</AcademyCompositionContext.Provider></AcademyContext.Provider>;
}
