import { learningDescription } from "../../utils/elearningPresentation";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowLeft, ArrowUp, ArrowDown, BookOpen, Plus } from "lucide-react";
import { DASHBOARD_ROUTES } from "../../config/routes";
import { fetchContent, executeContentCommand, uploadContentMedia } from "../../services/elearningContent";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import ELearningSkeleton from "./ELearningSkeleton";
import ELearningDialog from "./ELearningDialog";
import ContentBlockRenderer from "./content/ContentBlockRenderer";
import AssessmentBuilder from "./content/AssessmentBuilder";
import ContentBlockEditor from "./content/ContentBlockEditor";
import "../../styles/admin/dashboard/elearning-content.css";

function errorKey(failure) {
  const code = failure.detail?.code || failure.code;
  if (code === "elearning_content_conflict") return "conflict";
  if (code === "elearning_content_parent_archived") return "archivedParent";
  if (code === "elearning_content_upgrade_required") return "upgradeRequired";
  return failure.status === 404 ? "notFound" : failure.status === 403 ? "forbidden" : failure.status === 400 || failure.status === 422 ? "invalidContent" : "saveError";
}

export default function ELearningLessonPage() {
  const { courseId, lessonId } = useParams();
  return <LessonBuilder key={`${courseId}:${lessonId}`} courseId={courseId} lessonId={lessonId} />;
}

function LessonBuilder({ courseId, lessonId }) {
  const { t, i18n } = useTranslation("dashboard");
  const { labels, loading: labelsLoading } = useELearningTerminology();
  const [state, setState] = useState({ data: null, loading: true, error: "" });
  const [reload, setReload] = useState(0);
  const [busy, setBusy] = useState(false);
  const [editor, setEditor] = useState(null);
  const [dialog, setDialog] = useState(null);
  const [preview, setPreview] = useState(false);
  const [notice, setNotice] = useState("");
  useEffect(() => {
    let cancelled = false;
    fetchContent(courseId, lessonId).then((data) => { if (!cancelled) setState({ data, loading: false, error: "" }); })
      .catch((failure) => { if (!cancelled) setState({ data: null, loading: false, error: errorKey(failure) === "saveError" ? "loadError" : errorKey(failure) }); });
    return () => { cancelled = true; };
  }, [courseId, lessonId, reload]);
  const { data, loading, error } = state;
  const active = data?.blocks.filter((block) => !block.archived_at) || [];
  const archived = data?.blocks.filter((block) => block.archived_at) || [];
  const disabled = busy || !data?.editable || ["conflict", "archivedParent"].includes(error);
  async function run(action, block = null, payload = {}) {
    if (disabled) return;
    setBusy(true); setState((previous) => ({ ...previous, error: "" })); setNotice("");
    try {
      const result = await executeContentCommand(courseId, lessonId, { action, entity_id: block?.id || null, expected_revision: data.revision, payload });
      setState({ data: result, loading: false, error: "" }); setEditor(null); setDialog(null); setNotice("saved");
    } catch (failure) { setState((previous) => ({ ...previous, error: errorKey(failure) })); }
    finally { setBusy(false); }
  }
  function refresh() { setEditor(null); setDialog(null); setState({ data: null, loading: true, error: "" }); setReload((value) => value + 1); }
  if (loading || labelsLoading) return <ELearningSkeleton variant="lesson" label={t("elearning.content.loading")} direction={i18n.dir()} lang={i18n.language} />;
  function confirm(action, block) { setState((previous) => ({ ...previous, error: "" })); setDialog({ action, block }); }
  return <main className="ecommerce-page elearning-management elearning-content-page" dir={i18n.dir()} lang={i18n.language}>
    <header className="ecommerce-page-header app-page-intro"><div><h1>{t("elearning.structure.lessonBuilder")}</h1><p>{data?.lesson.name || t("elearning.navigation.courses")}</p></div></header>
    <nav className="elearning-content-breadcrumb" aria-label={t("elearning.content.breadcrumb")}><Link to={`${DASHBOARD_ROUTES.elearningCourses}/${courseId}`}>{labels.course || t("elearning.content.course")}</Link><span aria-hidden="true">/</span><Link to={`${DASHBOARD_ROUTES.elearningCourses}/${courseId}/structure`}>{t("elearning.courses.tabs.structure")}</Link><span aria-hidden="true">/</span><span aria-current="page">{data?.lesson.name || labels.lesson}</span></nav>
    <Link className="ecommerce-secondary-button elearning-back-link" to={`${DASHBOARD_ROUTES.elearningCourses}/${courseId}/structure`}><ArrowLeft size={16} aria-hidden="true" />{t("elearning.structure.back")}</Link>
    {error && <p role="alert" className="elearning-feedback is-error">{t(`elearning.content.${error}`)} <button className="ecommerce-secondary-button" disabled={busy} onClick={refresh}>{t("elearning.retry")}</button></p>}
    {notice && <p role="status" className="elearning-feedback">{t(`elearning.content.${notice}`)}</p>}
    {data && <>
      <section className="ecommerce-list-card elearning-course-overview"><header><h2>{data.lesson.name}</h2><span className={`elearning-course-status is-${data.lesson.status}`}>{t(`elearning.courses.statuses.${data.lesson.status}`)}</span></header><p>{learningDescription(data.lesson.description) || t("elearning.courses.noDescription")}</p><p>{t("elearning.structure.lessonContext", { section: labels.section, name: data.section.name })}</p></section>
      <section aria-label={t("elearning.content.context", { label: labels.lesson })} aria-busy={busy}>
        <header className="elearning-structure-header"><div><h2>{t("elearning.content.context", { label: labels.lesson })}</h2><p>{t("elearning.content.publication")}</p></div><div className="elearning-content-toolbar"><button className="ecommerce-secondary-button" disabled={busy || !active.length} onClick={() => setPreview(true)}>{t("elearning.content.previewLesson", { label: labels.lesson })}</button><button className="ecommerce-primary-button" disabled={disabled} onClick={() => setDialog({ action: "add" })}><Plus size={17} aria-hidden="true" />{t("elearning.content.add")}</button></div></header>
        {!data.editable && <p role="status" className="elearning-feedback">{t("elearning.content.archivedParent")}</p>}
        {!active.length && <div className="ecommerce-list-card ecommerce-empty-state"><BookOpen size={36} aria-hidden="true" /><h3>{t("elearning.content.empty")}</h3><p>{t("elearning.content.emptyHelp", { label: labels.lesson })}</p><button className="ecommerce-primary-button" disabled={disabled} onClick={() => setDialog({ action: "add" })}>{t("elearning.content.add")}</button></div>}
        <ol className="elearning-content-list">{active.map((block, index) => <li className="ecommerce-list-card elearning-block-card" key={block.id}>
          <header><h3>{index + 1}. {t(`elearning.content.types.${block.type}`, { defaultValue: block.type })}</h3><div className="elearning-content-toolbar">
            <button className="ecommerce-icon-button" aria-label={t("elearning.content.moveUp", { position: index + 1 })} disabled={disabled || index === 0} onClick={() => run("reorder", block, { direction: "up" })}><ArrowUp size={17} aria-hidden="true" /></button>
            <button className="ecommerce-icon-button" aria-label={t("elearning.content.moveDown", { position: index + 1 })} disabled={disabled || index === active.length - 1} onClick={() => run("reorder", block, { direction: "down" })}><ArrowDown size={17} aria-hidden="true" /></button>
            <button className="ecommerce-secondary-button" disabled={disabled} onClick={() => { setState((previous) => ({ ...previous, error: "" })); setEditor({ block, type: block.type }); }}>{t("elearning.content.edit")}</button>
            <button className="ecommerce-secondary-button" disabled={disabled} onClick={() => run("duplicate", block)}>{t("elearning.courses.duplicate")}</button>
            <button className="ecommerce-secondary-button" disabled={disabled} onClick={() => confirm("archive", block)}>{t("elearning.courses.archive")}</button>
            <button className="ecommerce-secondary-button" disabled={disabled} onClick={() => confirm("delete", block)}>{t("elearning.content.delete")}</button>
          </div></header><ContentBlockRenderer block={block} />
        </li>)}</ol>
        {archived.length > 0 && <details className="ecommerce-list-card elearning-archived-blocks"><summary>{t("elearning.content.archived", { count: archived.length })}</summary>{archived.map((block) => <div className="elearning-content-toolbar" key={block.id}><span>{block.title || t(`elearning.content.types.${block.type}`)}</span><button className="ecommerce-secondary-button" disabled={disabled} onClick={() => run("restore", block)}>{t("elearning.content.restore")}</button><button className="ecommerce-secondary-button" disabled={disabled} onClick={() => confirm("delete", block)}>{t("elearning.content.delete")}</button></div>)}</details>}
      </section>
    </>}
    {dialog?.action === "add" && <ELearningDialog title={t("elearning.content.add")} onClose={() => setDialog(null)} closeLabel={t("elearning.courses.close")}><div className="elearning-block-choices">{["text", "audio", "video", "assessment"].map((type) => <button className="ecommerce-secondary-button" key={type} onClick={() => { setDialog(null); setEditor({ type }); }}>{t(`elearning.content.types.${type}`)}</button>)}</div></ELearningDialog>}
    {editor?.type === "assessment" && <AssessmentBuilder courseId={courseId} lessonId={lessonId} block={editor.block} revision={data.revision} onClose={() => setEditor(null)} onSaved={refresh} />}
    {editor && editor.type !== "assessment" && <ContentBlockEditor block={editor.block} type={editor.type} busy={busy} error={error} upload={(file) => uploadContentMedia(courseId, lessonId, file)} onClose={() => setEditor(null)} onSave={(payload) => run(editor.block ? "update" : "create", editor.block, payload)} />}
    {dialog && ["archive", "delete"].includes(dialog.action) && <ELearningDialog title={t(`elearning.content.${dialog.action}Title`)} busy={busy} onClose={() => setDialog(null)} closeLabel={t("elearning.courses.close")}>
      <p>{t(`elearning.content.${dialog.action}Help`, { name: dialog.block.title || t(`elearning.content.types.${dialog.block.type}`) })}</p>{error && <p role="alert">{t(`elearning.content.${error}`)}</p>}
      <footer><button className="ecommerce-secondary-button" disabled={busy} onClick={() => setDialog(null)}>{t("elearning.courses.cancel")}</button><button className="ecommerce-primary-button" disabled={disabled} onClick={() => run(dialog.action, dialog.block, { confirmed: true })}>{t(dialog.action === "delete" ? "elearning.content.delete" : "elearning.courses.archive")}</button></footer>
    </ELearningDialog>}
    {preview && <ELearningDialog title={t("elearning.content.previewLesson", { label: labels.lesson })} onClose={() => setPreview(false)} closeLabel={t("elearning.courses.close")}><div className="elearning-lesson-preview">{active.map((block) => <ContentBlockRenderer key={block.id} block={block} context="preview" courseId={courseId} lessonId={lessonId} />)}</div></ELearningDialog>}
  </main>;
}
