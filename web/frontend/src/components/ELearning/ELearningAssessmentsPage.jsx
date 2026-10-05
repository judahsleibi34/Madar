import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { fetchPlacements, attachAssessment, placementCommand, commandAssessment } from "../../services/elearningAssessments";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import AssessmentBuilder from "./content/AssessmentBuilder";
import ContentBlockRenderer from "./content/ContentBlockRenderer";
import ELearningDialog from "./ELearningDialog";
import ELearningSkeleton from "./ELearningSkeleton";
import "../../styles/admin/dashboard/elearning-content.css";
export default function ELearningAssessmentsPage({ course, section }) {
  const { t } = useTranslation("dashboard"), { labels } = useELearningTerminology();
  const [data, setData] = useState(null), [reload, setReload] = useState(0), [error, setError] = useState(""), [busy, setBusy] = useState(false), [editor, setEditor] = useState(null), [dialog, setDialog] = useState(null), [selected, setSelected] = useState(""), [required, setRequired] = useState(false);
  useEffect(() => {
    let active = true;
    fetchPlacements(course.id, section?.id).then(value => { if (active) setData(value); }).catch(failure => { if (active) setError(failure.detail?.message || t("elearning.assessment.loadError")); });
    return () => { active = false; };
  }, [course.id, section?.id, reload, t]);
  function refresh() { setEditor(null); setDialog(null); setError(""); setReload(value => value + 1); }
  async function run(action, placement) {
    setBusy(true); setError("");
    try {
      if (action === "attach") await attachAssessment(course.id, { assessment_id: selected, section_id: section?.id || null, expected_revision: data.revision, required_for_completion: required });
      else if (action === "archive") await commandAssessment(course.id, null, placement.id, { action: "settings", expected_revision: placement.assessment.revision, payload: { title: placement.assessment.title, instructions: placement.assessment.instructions, passing_score: Number(placement.assessment.passing_score), max_attempts: placement.assessment.max_attempts, required_for_completion: placement.required_for_completion, status: "archived" } });
      else await placementCommand(course.id, placement.id, { action, expected_revision: data.revision, confirmed: action === "remove" });
      refresh();
    } catch (failure) { setError(failure.detail?.message || t("elearning.assessment.saveError")); } finally { setBusy(false); }
  }
  const label = labels[section ? "section" : "course"];
  return <section className="elearning-assessments-page">
    <header className="elearning-structure-header"><div><h2>{t("elearning.placements.heading", { label })}</h2>{section && <p>{section.name}</p>}</div><div className="elearning-content-toolbar"><button className="ecommerce-primary-button" disabled={!data || busy || course.status === "archived" || section?.status === "archived"} onClick={() => setEditor({})}>{t("elearning.placements.add")}</button><button className="ecommerce-secondary-button" disabled={!data || busy} onClick={() => setDialog({ action: "attach" })}>{t("elearning.placements.attach")}</button></div></header>
    {error && <p role="alert">{error} <button onClick={refresh}>{t("elearning.retry")}</button></p>}
    {!data && !error && <ELearningSkeleton variant="course" label={t("elearning.assessment.loading")} />}
    {data?.placements.length === 0 && <p>{t("elearning.placements.empty")}</p>}
    {data?.placements.map(placement => <article key={placement.id} className="ecommerce-list-card assessment-placement-card"><h3>{placement.assessment.title}</h3><p><span className={`elearning-course-status is-${placement.assessment.status}`}>{t(`elearning.courses.statuses.${placement.assessment.status}`)}</span> · {t(`elearning.placements.${placement.required_for_completion ? "required" : "optional"}`)} · {t("elearning.assessment.passing")}: {placement.assessment.passing_score}% · {t("elearning.assessment.attempts")}: {placement.attempts}</p><div className="elearning-content-toolbar">
      {!placement.archived_at ? <><button disabled={busy} onClick={() => setEditor({ block: { id: placement.id, type: "assessment", assessment: placement.assessment } })}>{t("elearning.content.edit")}</button><button disabled={busy} onClick={() => setDialog({ action: "preview", placement })}>{t("elearning.placements.preview")}</button><button disabled={busy} onClick={() => run("duplicate", placement)}>{t("elearning.courses.duplicate")}</button><button disabled={busy} onClick={() => setDialog({ action: "archive", placement })}>{t("elearning.courses.archive")}</button><button disabled={busy} onClick={() => setDialog({ action: "remove", placement })}>{t("elearning.placements.remove")}</button></> : <><span>{t("elearning.placements.removed")}</span><button disabled={busy} onClick={() => run("restore", placement)}>{t("elearning.content.restore")}</button></>}
    </div></article>)}
    {editor && <AssessmentBuilder courseId={course.id} sectionId={section?.id} block={editor.block} revision={data.revision} onClose={() => setEditor(null)} onSaved={refresh} />}
    {dialog && <ELearningDialog title={t(`elearning.placements.${dialog.action}`)} busy={busy} onClose={() => setDialog(null)} closeLabel={t("elearning.courses.close")}>
      {dialog.action === "preview" ? <ContentBlockRenderer block={{ id: dialog.placement.id, type: "assessment", assessment: dialog.placement.assessment }} context="preview" courseId={course.id} /> : dialog.action === "attach" ? <form className="assessment-attach-form" onSubmit={event => { event.preventDefault(); run("attach"); }}><label>{t("elearning.content.types.assessment")}<select aria-label={t("elearning.content.types.assessment")} required disabled={busy} value={selected} onChange={event => setSelected(event.target.value)}><option value="">{t("elearning.placements.select")}</option>{data.available_assessments.map(value => <option key={value.id} value={value.id}>{value.title}</option>)}</select></label><label className="assessment-attach-choice"><input type="checkbox" disabled={busy} checked={required} onChange={event => setRequired(event.target.checked)} />{t("elearning.assessment.required", { lesson: label })}</label><p>{t("elearning.placements.shared")}</p><footer><button type="button" className="ecommerce-secondary-button" disabled={busy} onClick={() => setDialog(null)}>{t("elearning.courses.cancel")}</button><button type="submit" className="ecommerce-primary-button" disabled={busy || !selected}>{t("elearning.placements.attach")}</button></footer></form> : <><p>{t(`elearning.placements.${dialog.action}Help`)}</p><footer><button disabled={busy} onClick={() => setDialog(null)}>{t("elearning.courses.cancel")}</button><button disabled={busy} onClick={() => run(dialog.action, dialog.placement)}>{t("elearning.assessment.confirm")}</button></footer></>}
    </ELearningDialog>}
  </section>;
}
