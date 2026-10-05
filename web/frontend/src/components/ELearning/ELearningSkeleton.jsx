import PageHeaderSkeleton from "../common/PageHeaderSkeleton";
import LoadingBar from "../common/LoadingBar";
import "../../styles/admin/dashboard/elearning.css";
import "../../styles/admin/dashboard/elearning-management.css";
import "../../styles/admin/dashboard/elearning-skeleton.css";

function Line({ shape = "" }) {
  return <i className={`skeleton-line elearning-skeleton-line ${shape}`} />;
}

function EmptyPanel({ actions = 1 }) {
  return <section className="ecommerce-list-card ecommerce-empty-state">
    <Line shape="is-icon" /><Line shape="is-title" /><Line />
    {actions > 0 && <div className="elearning-course-actions">{Array.from({ length: actions }, (_, index) => <Line key={index} shape="is-button" />)}</div>}
  </section>;
}

function SettingsPanels() {
  const fields = {
    general: ["is-input", "is-textarea"],
    structure: ["is-switch", "is-switch", "is-switch"],
    assessments: ["is-switch", "is-input", "is-switch"],
    appearance: ["is-input", "is-input"],
  };
  return <div className="elearning-form">
    {["general", "terminology", "structure", "assessments", "appearance"].map((section) => <section className={`settings-card${section === "appearance" ? " elearning-branding-card" : ""}`} key={section}>
      <header className="elearning-card-heading"><Line shape="is-icon" /><div className="elearning-skeleton-copy"><Line shape="is-title" /><Line /></div></header>
      <div className="settings-form-grid">
        {section === "terminology" ? <div className="elearning-terminology">{[3, 2].map((count, index) => <div key={index} className={`elearning-terminology-group ${index === 0 ? "is-content" : "is-participants"}`}><Line shape="is-title" /><div className="elearning-terminology-fields">{Array.from({ length: count }, (_, field) => <div className="elearning-skeleton-copy" key={field}><Line /><Line shape="is-input" /></div>)}</div></div>)}</div>
          : fields[section].map((shape, index) => <div className={`settings-wide-field ${shape === "is-switch" ? "elearning-toggle" : "elearning-skeleton-copy"}`} key={index}>
            <Line /><Line shape={shape} />
            {section === "appearance" && index === 1 && <div className="elearning-logo-upload"><Line shape="is-button" /></div>}
          </div>)}
      </div>
    </section>)}
    <div className="elearning-actions"><Line shape="is-button" /></div>
  </div>;
}

export default function ELearningSkeleton({ variant = "courses", tab = "overview", label = "Loading E-learning", lang = "en", direction = lang === "ar" ? "rtl" : "ltr" }) {
  const settings = variant === "settings";
  return <main className={`${settings ? "settings-page elearning-settings" : "ecommerce-page elearning-management"} elearning-skeleton ${variant === "courses" ? "elearning-courses-page" : ""}`} dir={direction} lang={lang} aria-busy="true">
    <PageHeaderSkeleton className={`${settings ? "settings-header" : "ecommerce-page-header"} app-page-intro`} />
    <LoadingBar label={label} mode="inline" />
    <div className="elearning-skeleton-content" aria-hidden="true">
      {settings ? <SettingsPanels /> : variant === "courses" ? <>
        <div className="elearning-course-toolbar"><Line shape="is-button" /></div>
        <div className="elearning-course-grid">{Array.from({ length: 4 }, (_, index) => <article className="ecommerce-list-card elearning-course-card" key={index}>
          <div className="elearning-course-body"><div className="elearning-course-card-heading"><Line shape="is-icon elearning-course-thumbnail" /><div className="elearning-course-heading-copy"><Line shape="is-title" /><div className="elearning-course-badges"><Line shape="is-badge" /><Line shape="is-badge" /></div></div></div><Line /><Line />
            <div className="elearning-course-counts">{Array.from({ length: 3 }, (_, count) => <div className="elearning-skeleton-copy" key={count}><Line shape="is-badge" /><Line shape="is-icon" /></div>)}</div>
            <Line /><div className="elearning-course-actions"><Line shape="is-button" /><div className="elearning-course-icon-actions">{[0,1,2,3].map((action) => <Line shape="is-icon" key={action} />)}</div></div>
          </div>
        </article>)}</div>
      </> : ["groups", "instructors"].includes(variant) ? <>
        <div className="elearning-course-toolbar"><Line shape="is-button" /></div>
        <div className="elearning-course-grid">{Array.from({ length: 4 }, (_, index) => <article className="ecommerce-list-card elearning-directory-card" key={index}><div className="elearning-course-body"><Line shape="is-icon" /><Line shape="is-title" />{variant === "instructors" && <Line />}<Line /><Line /><div className="elearning-course-actions"><Line shape="is-button" /><Line shape="is-button" /></div></div></article>)}</div>
      </> : variant === "course" ? <>
        <Line shape="is-button elearning-back-link" />
        <div className="elearning-course-tabs">{Array.from({ length: 7 }, (_, index) => <Line key={index} shape="is-button" />)}</div>
        {tab === "overview" ? <section className="ecommerce-list-card elearning-course-overview"><header><Line shape="is-title" /><Line shape="is-button" /></header><Line shape="elearning-course-cover elearning-overview-cover" /><Line /><Line /><div className="elearning-course-counts">{Array.from({ length: 5 }, (_, index) => <div className="elearning-skeleton-copy" key={index}><Line shape="is-badge" /><Line shape="is-badge" /></div>)}</div><Line /></section> : tab === "structure" ? <StructurePanels /> : ["progress", "learners"].includes(tab) ? <ProgressPanels count={tab === "learners" ? 4 : 5} /> : <EmptyPanel actions={tab === "settings" ? 1 : 0} />}
      </> : variant === "lesson" ? <><EmptyPanel actions={0} /><StructurePanels /></> : <EmptyPanel />}
    </div>
  </main>;
}

export function ELearningRouteSkeleton({ pathname = "", ...props }) {
  const [, page = "courses", courseId, tab = "overview"] = pathname.split("/").filter(Boolean);
  return <ELearningSkeleton {...props} variant={page === "courses" && courseId ? tab === "lessons" ? "lesson" : "course" : page} tab={tab} />;
}

function StructurePanels() {
  return <div className="elearning-structure"><div className="elearning-structure-header"><Line shape="is-title" /><Line shape="is-button" /></div>{[0, 1].map((section) => <div className="ecommerce-list-card elearning-section-card" key={section}><header><Line shape="is-title" /><Line shape="is-button" /></header><Line />{[0, 1].map((lesson) => <div className="elearning-skeleton-copy" key={lesson}><Line /><Line shape="is-badge" /></div>)}<Line shape="is-button" /></div>)}</div>;
}

export function ELearningStructureSkeleton({ label }) {
  return <section className="elearning-skeleton" aria-busy="true"><LoadingBar mode="inline" label={label} /><div aria-hidden="true"><StructurePanels /></div></section>;
}

function ProgressPanels({ count = 5 }) {
  return <div className={`elearning-skeleton-copy ${count === 4 ? "elearning-learners-page" : ""}`}><div className="elearning-progress-overview">{Array.from({ length: count }, (_, index) => <div className="ecommerce-list-card" key={index}><Line shape="is-badge" /><Line shape="is-title" /></div>)}</div><div className="elearning-progress-tools">{Array.from({ length: count === 4 ? 4 : 2 }, (_, index) => <Line shape="is-input" key={index} />)}</div><div className="ecommerce-list-card elearning-progress-skeleton-rows">{Array.from({ length: 7 }, (_, index) => <Line shape="is-input" key={index} />)}</div></div>;
}
export function ELearningProgressSkeleton({ label, count = 5 }) {
  return <section className="elearning-skeleton" aria-busy="true"><LoadingBar mode="inline" label={label} /><div aria-hidden="true"><ProgressPanels count={count} /></div></section>;
}
