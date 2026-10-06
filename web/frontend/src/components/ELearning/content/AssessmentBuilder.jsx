import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowLeft, Pencil, Copy, ArrowUp, ArrowDown, Archive, ArchiveRestore, Trash2 } from "lucide-react";
import { loadAssessment, createAssessment, commandAssessment } from "../../../services/elearningAssessments";
import { fetchAudioMedia, uploadContentMedia } from "../../../services/elearningContent";
import { useELearningTerminology } from "../../../hooks/useELearningTerminology";
import ELearningDialog from "../ELearningDialog";
import ELearningSkeleton from "../ELearningSkeleton";
import MediaBlockRenderer from "./MediaBlockRenderer";
const types = ["multiple_choice", "true_false", "matching", "listen_match"];
const uuid = () => crypto.randomUUID();
const option = () => ({ id: uuid(), label: "" });
function fresh(type) {
  const left = [option(), option()], right = [option(), option()];
  return { type, prompt: "", points: 1, config: type === "multiple_choice" ? { options: left, correct_option_id: left[0].id } : type === "true_false" ? { correct_answer: true } : { prompts: type === "listen_match" ? left.map(v => ({ id: v.id, media_id: "", admin_label: "" })) : left, targets: right, correct_pairs: Object.fromEntries(left.map((v, i) => [v.id, right[i].id])) } };
}
const details = value => ({ title: value.title, instructions: value.instructions, passing_score: Number(value.passing_score), max_attempts: value.max_attempts === "" || value.max_attempts == null ? null : Number(value.max_attempts), required_for_completion: value.required_for_completion, status: value.status });
const questionPayload = q => ({ type: q.type, prompt: q.prompt, points: Number(q.points), config: q.config });
function QuestionAction({ icon: Icon, label, disabled, onClick, danger = false }) {
  return <button className={`ecommerce-secondary-button assessment-question-action${danger ? " is-danger" : ""}`} type="button" aria-label={label} title={label} disabled={disabled} onClick={onClick}><Icon size={18} aria-hidden="true" /></button>;
}
export default function AssessmentBuilder({ courseId, lessonId, sectionId, block, revision, onClose, onSaved }) {
  const { t } = useTranslation("dashboard"), { labels } = useELearningTerminology();
  const placementType = lessonId ? "lesson" : sectionId ? "section" : "course";
  const [state, setState] = useState(block ? null : { assessment: { title: "", instructions: "", passing_score: 70, max_attempts: null, required_for_completion: false, status: "draft" }, questions: [] });
  const [settings, setSettings] = useState(block ? null : details({ title: "", instructions: "", passing_score: 70, max_attempts: null, required_for_completion: false, status: "draft" })), [edit, setEdit] = useState(null), [busy, setBusy] = useState(false), [error, setError] = useState(""), [confirm, setConfirm] = useState(null), [media, setMedia] = useState([]);
  const [questionDrafts, setQuestionDrafts] = useState({});
  const editKey = edit?.question?.id || edit?.type;
  useEffect(() => {
    let active = true;
    if (block) loadAssessment(courseId, lessonId, block.id).then(data => { if (active) { setState(data); setSettings(details(data.assessment)); } }).catch(() => { if (active) setError(t("elearning.assessment.loadError")); });
    fetchAudioMedia(courseId, lessonId).then(data => { if (active) setMedia(data.media); }).catch(() => {});
    return () => { active = false; };
  }, [courseId, lessonId, block, t]);
  async function command(action, q, payload = {}) {
    setBusy(true); setError("");
    try {
      if (state.block_id) {
        const next = await commandAssessment(courseId, lessonId, state.block_id, { action, question_id: q?.id || null, expected_revision: state.assessment.revision, payload });
        setState(next); setSettings(previous => ({ ...previous, status: next.assessment.status }));
      } else {
        let questions = [...state.questions];
        const index = questions.findIndex(v => v.id === q?.id);
        if (action === "create_question") questions.push({ ...payload, id: uuid() });
        if (action === "update_question") questions[index] = { ...payload, id: q.id };
        if (action === "duplicate_question") questions.splice(index + 1, 0, { ...structuredClone(q), id: uuid() });
        if (action === "delete_question") questions.splice(index, 1);
        if (action === "archive_question" || action === "restore_question") questions[index] = { ...q, archived_at: action === "archive_question" ? new Date().toISOString() : null };
        if (action === "reorder_question") { const next = index + (payload.direction === "up" ? -1 : 1); [questions[index], questions[next]] = [questions[next], questions[index]]; }
        setState(previous => ({ ...previous, assessment: details(settings), questions: questions.sort((a, b) => Number(Boolean(a.archived_at)) - Number(Boolean(b.archived_at))) }));
      }
      if (editKey) setQuestionDrafts(previous => { const next = { ...previous }; delete next[editKey]; return next; });
      setEdit(null); setConfirm(null);
    } catch (failure) { setError(failure.detail?.message || t("elearning.assessment.saveError")); } finally { setBusy(false); }
  }
  async function save(event) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      if (state.block_id) await commandAssessment(courseId, lessonId, state.block_id, { action: "settings", expected_revision: state.assessment.revision, payload: details(settings) });
      else await createAssessment(courseId, lessonId, { expected_revision: revision, ...(!lessonId ? { section_id: sectionId || null } : {}), assessment: details(settings), questions: state.questions.filter(q => !q.archived_at).map(questionPayload) });
      onSaved();
    } catch (failure) { setError(failure.detail?.message || t("elearning.assessment.saveError")); } finally { setBusy(false); }
  }
  const field = (key, value) => setSettings(previous => ({ ...previous, [key]: value }));
  const active = state?.questions.filter(q => !q.archived_at) || [];
  return <ELearningDialog className="assessment-builder-dialog" title={t("elearning.assessment.builder")} busy={busy} onClose={onClose} closeLabel={t("elearning.courses.close")}>
    <div className="assessment-builder-body">
    {error && <p role="alert">{error}</p>}
    {!state || !settings ? <ELearningSkeleton label={t("elearning.assessment.loading")} /> : <>
      {edit ? <QuestionEditor key={editKey} question={questionDrafts[editKey] || edit.question || fresh(edit.type)} media={media} upload={async file => { const result = await uploadContentMedia(courseId, lessonId, file); const value = result.asset || { id: result.asset_id, url: result.asset_url, filename: file.name }; setMedia(previous => [value, ...previous]); return value; }} busy={busy} onBack={q => { setQuestionDrafts(previous => ({ ...previous, [editKey]: q })); setEdit(null); }} onCancel={() => { setQuestionDrafts(previous => { const next = { ...previous }; delete next[editKey]; return next; }); setEdit(null); }} onSave={q => command(edit.question ? "update_question" : "create_question", edit.question, q)} /> : <>
        <form id="assessment-settings" onSubmit={save} className="assessment-settings">
          <label className="assessment-field-wide">{t("elearning.assessment.title")}<input required maxLength={120} value={settings.title} onChange={e => field("title", e.target.value)} /></label>
          <label className="assessment-field-wide">{t("elearning.assessment.instructions")}<textarea aria-label={t("elearning.assessment.instructions")} maxLength={10000} value={settings.instructions} onChange={e => field("instructions", e.target.value)} /></label>
          <label>{t("elearning.assessment.passing")}<input type="number" required min="0" max="100" step="0.01" value={settings.passing_score} onChange={e => field("passing_score", e.target.value)} /></label>
          <label>{t("elearning.assessment.maxAttempts")}<input type="number" min="1" max="10000" placeholder={t("elearning.assessment.unlimited")} value={settings.max_attempts ?? ""} onChange={e => field("max_attempts", e.target.value)} /></label>
          <label className="assessment-choice"><input type="checkbox" checked={settings.required_for_completion} onChange={e => field("required_for_completion", e.target.checked)} />{t("elearning.assessment.required", { lesson: labels[placementType] })}</label>
          <label>{t("elearning.assessment.status")}<select aria-label={t("elearning.assessment.status")} value={settings.status} onChange={e => field("status", e.target.value)}>{["draft", "published", "archived"].map(status => <option key={status} value={status}>{t(`elearning.courses.statuses.${status}`)}</option>)}</select></label>
        </form>
        <h3>{t("elearning.assessment.addQuestion")}</h3><div className="elearning-content-toolbar">{types.map(type => <button className="ecommerce-secondary-button" type="button" disabled={busy} key={type} onClick={() => setEdit({ type })}>{t(`elearning.assessment.types.${type}`)}</button>)}</div>
        {!active.length && <p>{t("elearning.assessment.empty")}</p>}
        <ol className="elearning-content-list">{active.map((q, i) => <li key={q.id} className="ecommerce-list-card"><h4>{t("elearning.assessment.question", { number: i + 1 })}: {q.prompt}</h4><div className="elearning-content-toolbar assessment-question-actions" role="group" aria-label={t("elearning.assessment.question", { number: i + 1 })}>
          <QuestionAction icon={Pencil} label={t("elearning.content.edit")} disabled={busy} onClick={() => setEdit({ question: q })} /><QuestionAction icon={Copy} label={t("elearning.courses.duplicate")} disabled={busy} onClick={() => command("duplicate_question", q)} />
          <QuestionAction icon={ArrowUp} label={t("elearning.assessment.up")} disabled={busy || i === 0} onClick={() => command("reorder_question", q, { direction: "up" })} /><QuestionAction icon={ArrowDown} label={t("elearning.assessment.down")} disabled={busy || i === active.length - 1} onClick={() => command("reorder_question", q, { direction: "down" })} />
          <QuestionAction icon={Archive} label={t("elearning.courses.archive")} disabled={busy} onClick={() => setConfirm({ action: "archive_question", question: q })} /><QuestionAction icon={Trash2} label={t("elearning.content.delete")} danger disabled={busy} onClick={() => setConfirm({ action: "delete_question", question: q })} />
        </div></li>)}</ol>
        {state.questions.filter(q => q.archived_at).map(q => <div className="assessment-archived-question" key={q.id}><p>{q.prompt}</p><div className="elearning-content-toolbar assessment-question-actions"><QuestionAction icon={ArchiveRestore} label={t("elearning.content.restore")} disabled={busy} onClick={() => command("restore_question", q)} /><QuestionAction icon={Trash2} label={t("elearning.content.delete")} danger disabled={busy} onClick={() => setConfirm({ action: "delete_question", question: q })} /></div></div>)}
        {confirm && <div role="alert"><p>{t("elearning.assessment.confirmDelete")}</p><button className="ecommerce-secondary-button" type="button" onClick={() => setConfirm(null)}>{t("elearning.courses.cancel")}</button><button className="ecommerce-secondary-button" type="button" disabled={busy} onClick={() => command(confirm.action, confirm.question, { confirmed: true })}>{t("elearning.assessment.confirm")}</button></div>}
      </>}
    </>}
    </div>
    {state && settings && !edit && <footer className="assessment-builder-footer"><button className="ecommerce-secondary-button" type="button" disabled={busy} onClick={onClose}>{t("elearning.courses.cancel")}</button><button className="ecommerce-primary-button" form="assessment-settings" disabled={busy}>{t("elearning.courses.save")}</button></footer>}
  </ELearningDialog>;
}
function QuestionEditor({ question, media, upload, busy, onBack, onCancel, onSave }) {
  const { t } = useTranslation("dashboard");
  const [q, setQ] = useState(() => structuredClone(question)), [uploading, setUploading] = useState(false), [error, setError] = useState("");
  const config = changes => setQ(previous => ({ ...previous, config: { ...previous.config, ...changes } }));
  const updateRow = (key, index, property, value) => config({ [key]: q.config[key].map((row, i) => i === index ? { ...row, [property]: value } : row) });
  async function uploadRow(index, file) {
    if (!file) return; setUploading(true); setError("");
    try { const value = await upload(file); updateRow("prompts", index, "media_id", value.id); } catch (failure) { setError(failure.detail?.message || t("elearning.content.mediaError")); } finally { setUploading(false); }
  }
  function addPair() {
    const left = q.type === "listen_match" ? { id: uuid(), media_id: "", admin_label: "" } : option(), right = option();
    config({ prompts: [...q.config.prompts, left], targets: [...q.config.targets, right], correct_pairs: { ...q.config.correct_pairs, [left.id]: right.id } });
  }
  function removePair(index) {
    const left = q.config.prompts[index], target = q.config.correct_pairs[left.id];
    const pairs = { ...q.config.correct_pairs }; delete pairs[left.id];
    config({ prompts: q.config.prompts.filter((_, i) => i !== index), targets: q.config.targets.filter(row => row.id !== target), correct_pairs: pairs });
  }
  return <form className="assessment-question-editor" onSubmit={e => { e.preventDefault(); onSave(questionPayload(q)); }}>
    <nav className="assessment-question-navigation" aria-label={t("elearning.assessment.builder")}><button className="ecommerce-secondary-button" type="button" disabled={busy || uploading} onClick={() => onBack(q)}><ArrowLeft size={18} aria-hidden="true" />{t("elearning.assessment.back")}</button><span>{t(`elearning.assessment.types.${q.type}`)}</span></nav>
    <div className="assessment-question-heading"><h3>{t(`elearning.assessment.types.${q.type}`)}</h3><p>{t("elearning.assessment.questionHelp")}</p></div>{error && <p role="alert">{error}</p>}
    <label>{t("elearning.assessment.prompt")}<textarea aria-label={t("elearning.assessment.prompt")} required maxLength={10000} value={q.prompt} onChange={e => setQ(previous => ({ ...previous, prompt: e.target.value }))} /></label>
    <label>{t("elearning.assessment.points")}<input type="number" required min="0.01" max="10000" step="0.01" value={q.points} onChange={e => setQ(previous => ({ ...previous, points: e.target.value }))} /></label>
    {q.type === "multiple_choice" && <>{q.config.options.map((row, i) => <div className="assessment-pair assessment-option-row" key={row.id}><label>{t("elearning.assessment.option", { number: i + 1 })}<input required maxLength={2000} value={row.label} onChange={e => updateRow("options", i, "label", e.target.value)} /></label><label><input type="radio" name="correct-option" checked={q.config.correct_option_id === row.id} onChange={() => config({ correct_option_id: row.id })} />{t("elearning.assessment.correct")}</label><button className="ecommerce-secondary-button" type="button" disabled={q.config.options.length <= 2} onClick={() => { const options = q.config.options.filter(v => v.id !== row.id); config({ options, correct_option_id: q.config.correct_option_id === row.id ? options[0].id : q.config.correct_option_id }); }}>{t("elearning.assessment.removeOption")}</button></div>)}<button className="ecommerce-secondary-button" type="button" disabled={q.config.options.length >= 20} onClick={() => config({ options: [...q.config.options, option()] })}>{t("elearning.assessment.addOption")}</button></>}
    {q.type === "true_false" && <label>{t("elearning.assessment.correct")}<select value={String(q.config.correct_answer)} onChange={e => config({ correct_answer: e.target.value === "true" })}><option value="true">{t("elearning.assessment.true")}</option><option value="false">{t("elearning.assessment.false")}</option></select></label>}
    {["matching", "listen_match"].includes(q.type) && <>{q.config.prompts.map((row, i) => { const target = q.config.targets.find(v => v.id === q.config.correct_pairs[row.id]), targetIndex = q.config.targets.findIndex(v => v.id === target.id), selected = media.find(v => v.id === row.media_id); return <div className="assessment-pair" key={row.id}>
      {q.type === "matching" ? <label>{t("elearning.assessment.left", { number: i + 1 })}<input required maxLength={2000} value={row.label} onChange={e => updateRow("prompts", i, "label", e.target.value)} /></label> : <div><label>{t("elearning.assessment.audio", { number: i + 1 })}<select aria-label={t("elearning.assessment.audio", { number: i + 1 })} required value={row.media_id} onChange={e => updateRow("prompts", i, "media_id", e.target.value)}><option value="">{t("elearning.assessment.selectMedia")}</option>{row.media_id && !selected && <option value={row.media_id}>{t("elearning.assessment.savedMedia")}</option>}{media.map(v => <option key={v.id} value={v.id}>{v.filename}</option>)}</select></label><label>{t("elearning.assessment.adminLabel")}<input maxLength={120} value={row.admin_label} onChange={e => updateRow("prompts", i, "admin_label", e.target.value)} /></label><label>{t("elearning.assessment.upload")}<input type="file" accept="audio/mpeg,audio/wav,.mp3,.wav" disabled={uploading} onChange={e => uploadRow(i, e.target.files[0])} /></label>{selected && <MediaBlockRenderer kind="audio" block={{ title: t("elearning.assessment.audio", { number: i + 1 }), media: selected }} />}</div>}
      <label>{t("elearning.assessment.right", { number: i + 1 })}<input required maxLength={2000} value={target.label} onChange={e => updateRow("targets", targetIndex, "label", e.target.value)} /></label><button className="ecommerce-secondary-button" type="button" disabled={q.config.prompts.length <= 2} onClick={() => removePair(i)}>{t("elearning.assessment.removePair")}</button>
    </div>; })}<button className="ecommerce-secondary-button" type="button" disabled={q.config.prompts.length >= 50} onClick={addPair}>{t("elearning.assessment.addPair")}</button></>}
    <footer><button className="ecommerce-secondary-button" type="button" disabled={busy || uploading} onClick={onCancel}>{t("elearning.courses.cancel")}</button><button className="ecommerce-primary-button" disabled={busy || uploading}>{t("elearning.assessment.saveQuestion")}</button></footer>
  </form>;
}
