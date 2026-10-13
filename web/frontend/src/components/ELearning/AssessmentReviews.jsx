import LearningErrorNotice from "./LearningErrorNotice";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { learningReviewRequest } from "../../services/elearningAssessments";
import { getApiUrl } from "../../utils/apiClient";

export default function AssessmentReviews() {
  const { attemptId } = useParams();
  const { i18n } = useTranslation();
  const ar = i18n.language.startsWith("ar");
  const copy = ar ? { student: "الطالب", title: "مراجعة التقييمات", open: "فتح", points: "النقاط", feedback: "ملاحظات المراجع", finalize: "حفظ التقييم البشري", next: "التالي", previous: "السابق", empty: "لا توجد إجابات بانتظار مراجعتك.", error: "تعذر تحميل المراجعة أو حفظها. أعد التحميل للتحقق من الحالة الحالية.", refresh: "تحديث", pending: "بانتظار المراجعة", done: "اكتمل التقييم", answer: "الإجابة", rubric: "معايير التقييم" } : { student: "Student", title: "Assessment reviews", open: "Open", points: "Points", feedback: "Reviewer feedback", finalize: "Save human grade", next: "Next", previous: "Previous", empty: "No responses awaiting your review.", error: "Could not load or save review. Refresh to check the current state.", refresh: "Refresh", pending: "Pending Review", done: "Grading complete", answer: "Answer", rubric: "Rubric" };
  const [items, setItems] = useState([]), [offset, setOffset] = useState(0), [detail, setDetail] = useState(null), [error, setError] = useState(""), [busy, setBusy] = useState(false), [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    learningReviewRequest(`assessment-reviews?limit=50&offset=${offset}`).then(value => { if (active) { setItems(value); setError(""); } }).catch(() => { if (active) setError(copy.error); });
    return () => { active = false; };
  }, [offset, refresh, copy.error]);
  useEffect(() => {
    if (!attemptId) return;
    let active = true;
    learningReviewRequest(`assessment-reviews/${encodeURIComponent(attemptId)}`).then(value => { if (active) setDetail(value); }).catch(() => { if (active) setError(copy.error); });
    return () => { active = false; };
  }, [attemptId, copy.error]);
  async function open(id) {
    setBusy(true); setError("");
    try { setDetail(await learningReviewRequest(`assessment-reviews/${encodeURIComponent(id)}`)); } catch { setError(copy.error); } finally { setBusy(false); }
  }
  async function grade(question, event) {
    event.preventDefault(); const form = new FormData(event.currentTarget);
    setBusy(true); setError("");
    try {
      const result = await learningReviewRequest(`assessment-reviews/${encodeURIComponent(detail.id)}/questions/${encodeURIComponent(question.id)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ expected_revision: detail.review_revision, points: Number(form.get("points")), feedback: form.get("feedback") }) });
      setDetail(result); setRefresh(value => value + 1);
    } catch { setError(copy.error); } finally { setBusy(false); }
  }
  return <main className="ecommerce-management" aria-busy={busy}>
    <h1>{copy.title}</h1>
    {error && <LearningErrorNotice as="p">{error}</LearningErrorNotice>}
    <button type="button" disabled={busy} onClick={() => { setRefresh(value => value + 1); if (detail) open(detail.id); }}>{copy.refresh}</button>
    {!items.length && <p>{copy.empty}</p>}
    <ul>{items.map(item => <li key={item.id}>{item.title} · {item.student_name || copy.student} <button type="button" disabled={busy} onClick={() => open(item.id)}>{copy.open}</button></li>)}</ul>
    <button type="button" disabled={busy || offset === 0} onClick={() => setOffset(value => Math.max(0, value - 50))}>{copy.previous}</button>
    <button type="button" disabled={busy || items.length < 50} onClick={() => setOffset(value => value + 50)}>{copy.next}</button>
    {detail && <section key={detail.id}>
      <h2>{detail.snapshot.assessment.title}</h2><p>{detail.student_name || copy.student}</p><p role="status">{detail.status === "pending_review" ? copy.pending : copy.done}</p>
      {detail.snapshot.questions.filter(question => ["written", "speaking"].includes(question.type)).map(question => {
        const answer = detail.answers.find(value => value.question_id === question.id);
        return <article className="ecommerce-list-card" key={question.id}>
          <h3>{question.prompt}</h3><p>{copy.rubric}: {question.config.rubric}</p>
          {question.type === "written" ? <p style={{ whiteSpace: "pre-wrap" }}>{copy.answer}: {answer?.response.text}</p> : answer?.response.recording_id && <audio controls preload="none" src={getApiUrl(`/elearning/assessment-recordings/${encodeURIComponent(answer.response.recording_id)}`)} aria-label={question.prompt} />}
          {answer?.review ? <p>{copy.points}: {answer.review.points} / {question.points}<br />{answer.review.feedback}</p> : <form onSubmit={event => grade(question, event)}>
            <label>{copy.points}<input name="points" type="number" required min="0" max={question.points} step="0.01" disabled={busy} /></label>
            <label>{copy.feedback}<textarea name="feedback" maxLength={10000} disabled={busy} /></label>
            <button disabled={busy || detail.status !== "pending_review"}>{copy.finalize}</button>
          </form>}
        </article>;
      })}
    </section>}
  </main>;
}
