import { learningDescription } from "../../utils/elearningPresentation";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Plus, ArrowUp, ArrowDown, BookOpen } from "lucide-react";
import { DASHBOARD_ROUTES } from "../../config/routes";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import { executeStructureCommand, fetchStructure } from "../../services/elearningStructure";
import { ELearningStructureSkeleton } from "./ELearningSkeleton";
import ELearningStructureForm from "./ELearningStructureForm";
import ELearningDialog from "./ELearningDialog";
import ELearningAssessmentsPage from "./ELearningAssessmentsPage";
import Actions from "./ELearningActions";

export default function ELearningStructurePage({ course, onUpdated }) {
  const { t } = useTranslation("dashboard");
  const { labels, error: labelsError } = useELearningTerminology();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState(false);
  const [reload, setReload] = useState(0);
  const [assessmentSection, setAssessmentSection] = useState(null);
  const [form, setForm] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [moving, setMoving] = useState(null);
  const [destination, setDestination] = useState("");
  useEffect(() => {
    let cancelled = false;
    fetchStructure(course.id).then((result) => { if (!cancelled) { setData(result); onUpdated(result); } })
      .catch((failure) => { if (!cancelled) setError(failure.status === 403 ? "forbidden" : failure.status === 404 ? "courses.notFound" : "structure.loadError"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [course.id, reload, onUpdated]);
  const closeDialogs = () => { setForm(null); setConfirm(null); setMoving(null); };
  const run = async (action, item, payload = {}) => {
    if (busy) return;
    setBusy(true); setError(""); setFeedback(false);
    try {
      const result = await executeStructureCommand(course.id, { action, expected_revision: data.revision, ...(item ? { entity_id: item.id } : {}), payload });
      setData(result); onUpdated(result); closeDialogs(); setFeedback(true);
    } catch (failure) {
      const code = failure.data?.detail?.code || failure.code;
      setError(code === "elearning_lesson_in_use" ? "structure.inUse" : code === "elearning_section_not_empty" ? "structure.notEmpty" : failure.status === 409 ? "structure.conflict" : failure.status === 403 ? "forbidden" : failure.status === 404 ? "structure.notFound" : [400, 422].includes(failure.status) ? "structure.validationError" : "structure.saveError");
    } finally { setBusy(false); }
  };
  const disabled = busy || !data?.available || error === "forbidden" || labelsError?.status === 403;
  const openForm = (kind, item, section) => { setError(""); setForm({ kind, item, section }); };
  const beginConfirm = (action, item, kind) => { setError(""); setConfirm({ action, item, kind }); };
  const sections = data?.sections || [];
  const destinations = sections.filter((section) => section.id !== moving?.section_id && section.status !== "archived");
  const actionButtons = (kind, item, section) => <>
    {kind === "section" && <button disabled={disabled || item.status === "archived"} onClick={() => setAssessmentSection(item)}>{t("elearning.courses.tabs.assessments")}</button>}
    {kind === "lesson" && <Link to={`${DASHBOARD_ROUTES.elearningCourses}/${course.id}/lessons/${item.id}`}>{t("elearning.structure.openContent")}</Link>}
    <button disabled={disabled} onClick={() => openForm(kind, item, section)}>{t(kind === "lesson" ? "elearning.structure.editDetails" : "elearning.courses.editAction")}</button>
    <button title={t("elearning.structure.duplicateHelp")} disabled={disabled || (kind === "lesson" && section.status === "archived")} onClick={() => run(`duplicate_${kind}`, item)}>{t("elearning.courses.duplicate")}</button>
    {kind === "lesson" && <button disabled={disabled || !sections.some((row) => row.id !== item.section_id && row.status !== "archived")} onClick={() => { setError(""); setMoving(item); setDestination(sections.find((row) => row.id !== item.section_id && row.status !== "archived")?.id || ""); }}>{t("elearning.structure.move")}</button>}
    {item.status !== "archived" && <button disabled={disabled} onClick={() => beginConfirm(`archive_${kind}`, item, kind)}>{t("elearning.courses.archive")}</button>}
    <button disabled={disabled || (kind === "section" && item.lessons.length > 0)} onClick={() => beginConfirm(`delete_${kind}`, item, kind)}>{t("elearning.structure.delete")}</button>
  </>;
  if (assessmentSection) return <section><button className="ecommerce-secondary-button" onClick={() => { setAssessmentSection(null); setReload(value => value + 1); }}>{t("elearning.structure.back")}</button><ELearningAssessmentsPage course={course} section={assessmentSection} /></section>;
  if (loading) return <ELearningStructureSkeleton label={t("elearning.structure.loading")} />;
  return <section className="elearning-structure" aria-labelledby="elearning-structure-title">
    <header className="elearning-structure-header"><div><h2 id="elearning-structure-title">{t("elearning.courses.tabs.structure")}</h2><p>{t("elearning.structure.subtitle", { label: labels.course })}</p></div><button className="ecommerce-primary-button" disabled={disabled} onClick={() => openForm("section")}><Plus size={17} aria-hidden="true" />{t("elearning.courses.add", { label: labels.section })}</button></header>
    {error && !form && !confirm && !moving && <p role="alert" className="elearning-feedback is-error">{t(`elearning.${error}`)} <button className="ecommerce-secondary-button" disabled={busy} onClick={() => { setError(""); setLoading(true); setReload((value) => value + 1); }}>{t("elearning.structure.reload")}</button></p>}
    {feedback && <p role="status" className="elearning-feedback">{t("elearning.structure.saved")}</p>}
    {!data?.available && !error && <p role="status" className="elearning-feedback">{t("elearning.structure.upgradeRequired")}</p>}
    {data?.available && <>
      <dl className="elearning-structure-summary"><div><dt>{labels.plural.section}</dt><dd>{data.section_count}</dd></div><div><dt>{labels.plural.lesson}</dt><dd>{data.lesson_count}</dd></div><div><dt>{t("elearning.courses.statuses.published")}</dt><dd>{data.published_count}</dd></div><div><dt>{t("elearning.courses.statuses.draft")}</dt><dd>{data.draft_count}</dd></div></dl>
      {sections.length === 0 ? <div className="ecommerce-list-card ecommerce-empty-state"><BookOpen size={36} aria-hidden="true" /><h3>{t("elearning.structure.empty", { labels: labels.plural.section })}</h3><p>{t("elearning.structure.emptyHelp", { section: labels.section, course: labels.course })}</p></div> : sections.map((section, index) => <article key={section.id} className="ecommerce-list-card elearning-section-card">
        <header><div className="elearning-structure-item-heading"><span className="elearning-structure-position">{t("elearning.structure.positionLabel", { label: labels.section, position: (section.position ?? index) + 1 })}</span><h3>{section.name}</h3><span className={`elearning-course-status is-${section.status}`}>{t(`elearning.courses.statuses.${section.status}`)}</span><span>{t("elearning.structure.lessonCount", { count: section.lessons.filter((lesson) => lesson.status !== "archived").length, labels: labels.plural.lesson })}</span></div>
          <div className="elearning-structure-controls"><button className="ecommerce-icon-button" disabled={disabled || index === 0} aria-label={t("elearning.structure.moveUp", { name: section.name })} onClick={() => run("reorder_section", section, { direction: "up" })}><ArrowUp size={17} /></button><button className="ecommerce-icon-button" disabled={disabled || index === sections.length - 1} aria-label={t("elearning.structure.moveDown", { name: section.name })} onClick={() => run("reorder_section", section, { direction: "down" })}><ArrowDown size={17} /></button><Actions label={t("elearning.structure.actions", { name: section.name })} disabled={disabled}>{actionButtons("section", section)}</Actions></div>
        </header>
        {section.description && <p className="elearning-course-description">{learningDescription(section.description)}</p>}
        <button className="ecommerce-secondary-button" disabled={disabled || section.status === "archived"} onClick={() => setAssessmentSection(section)}>{t("elearning.placements.heading", { label: labels.section })}</button>
        {section.status === "archived" && <p className="elearning-feedback">{t("elearning.structure.archivedSection")}</p>}
        {section.lessons.length === 0 ? <p className="elearning-structure-empty-section">{t("elearning.structure.emptySection", { lessons: labels.plural.lesson, section: labels.section })}</p> : <ol className="elearning-lesson-list">{section.lessons.map((lesson, lessonIndex) => <li key={lesson.id}><div className="elearning-lesson-copy"><span className="elearning-structure-position">{t("elearning.structure.positionLabel", { label: labels.lesson, position: (lesson.position ?? lessonIndex) + 1 })}</span><Link to={`${DASHBOARD_ROUTES.elearningCourses}/${course.id}/lessons/${lesson.id}`}>{lesson.name}</Link>{lesson.description && <p>{learningDescription(lesson.description)}</p>}<span className={`elearning-course-status is-${lesson.status}`}>{t(`elearning.courses.statuses.${lesson.status}`)}</span></div><div className="elearning-structure-controls"><Link className="ecommerce-secondary-button" to={`${DASHBOARD_ROUTES.elearningCourses}/${course.id}/lessons/${lesson.id}`}>{t("elearning.structure.openContent")}</Link><button className="ecommerce-icon-button" disabled={disabled || lessonIndex === 0} aria-label={t("elearning.structure.moveUp", { name: lesson.name })} onClick={() => run("reorder_lesson", lesson, { direction: "up" })}><ArrowUp size={17} /></button><button className="ecommerce-icon-button" disabled={disabled || lessonIndex === section.lessons.length - 1} aria-label={t("elearning.structure.moveDown", { name: lesson.name })} onClick={() => run("reorder_lesson", lesson, { direction: "down" })}><ArrowDown size={17} /></button><Actions label={t("elearning.structure.actions", { name: lesson.name })} disabled={disabled}>{actionButtons("lesson", lesson, section)}</Actions></div></li>)}</ol>}
        <footer><button className="ecommerce-secondary-button" disabled={disabled || section.status === "archived"} onClick={() => openForm("lesson", null, section)}><Plus size={17} aria-hidden="true" />{t("elearning.courses.add", { label: labels.lesson })}</button>{section.lessons.length > 0 && <small>{t("elearning.structure.deleteSectionHelp")}</small>}</footer>
      </article>)}
      {sections.length > 0 && <button className="ecommerce-secondary-button elearning-add-section" disabled={disabled} onClick={() => openForm("section")}><Plus size={17} aria-hidden="true" />{t("elearning.courses.add", { label: labels.section })}</button>}
    </>}
    {form && <ELearningStructureForm kind={form.kind} label={labels[form.kind]} item={form.item} position={form.item ? (form.item.position ?? (form.kind === "section" ? sections : form.section.lessons).findIndex((item) => item.id === form.item.id)) + 1 : (form.kind === "section" ? sections.length : form.section.lessons.length) + 1} busy={busy} error={error} onClose={() => setForm(null)} onSave={(details) => run(`${form.item ? "update" : "create"}_${form.kind}`, form.item, { ...details, ...(!form.item && form.kind === "lesson" ? { section_id: form.section.id } : {}) })} />}
    {confirm && <ELearningDialog title={t(confirm.action.startsWith("delete") ? "elearning.structure.deleteTitle" : "elearning.courses.archiveTitle", { label: labels[confirm.kind] })} busy={busy} onClose={() => setConfirm(null)} closeLabel={t("elearning.courses.close")}>{error && <p role="alert" className="elearning-feedback is-error">{t(`elearning.${error}`)}</p>}<p>{t(confirm.action.startsWith("delete") ? "elearning.structure.deleteHelp" : "elearning.structure.archiveHelp", { name: confirm.item.name })}</p><footer><button className="ecommerce-secondary-button" disabled={busy} onClick={() => setConfirm(null)}>{t("elearning.courses.cancel")}</button><button className="ecommerce-primary-button" disabled={busy} onClick={() => run(confirm.action, confirm.item, confirm.action.startsWith("delete") ? { confirmed: true } : {})}>{t(confirm.action.startsWith("delete") ? "elearning.structure.delete" : "elearning.courses.archive")}</button></footer></ELearningDialog>}
    {moving && <ELearningDialog title={t("elearning.structure.moveTitle", { label: labels.lesson })} busy={busy} onClose={() => setMoving(null)} closeLabel={t("elearning.courses.close")}><form onSubmit={(event) => { event.preventDefault(); if (!busy) run("move_lesson", moving, { section_id: destination }); }}>{error && <p role="alert" className="elearning-feedback is-error">{t(`elearning.${error}`)}</p>}<fieldset className="elearning-course-form" disabled={busy}><label>{t("elearning.structure.destination", { label: labels.section })}<select required value={destination} onChange={(event) => setDestination(event.target.value)}>{destinations.map((section) => <option value={section.id} key={section.id}>{section.name}</option>)}</select></label><p>{t("elearning.structure.moveHelp")}</p></fieldset><footer><button type="button" className="ecommerce-secondary-button" disabled={busy} onClick={() => setMoving(null)}>{t("elearning.courses.cancel")}</button><button type="submit" className="ecommerce-primary-button" disabled={busy || !destination}>{t("elearning.structure.move")}</button></footer></form></ELearningDialog>}
  </section>;
}
