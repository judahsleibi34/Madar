import { useTranslation } from "react-i18next";
import MediaBlockRenderer from "./MediaBlockRenderer";
export default function AssessmentQuestions({ questions, answers, onChange, disabled }) {
  const { t } = useTranslation("dashboard");
  return questions.map((q, index) => <fieldset className="ecommerce-list-card assessment-question" key={q.id} disabled={disabled}>
    <legend>{t("elearning.assessment.question", { number: index + 1 })}: {q.prompt}</legend>
    <small>{t("elearning.assessment.points")}: {q.points}</small>
    {q.type === "multiple_choice" && q.config.options.map(option => <label key={option.id}><input type="radio" name={q.id} checked={answers[q.id]?.option_id === option.id} onChange={() => onChange(q.id, { option_id: option.id })} />{option.label}</label>)}
    {q.type === "true_false" && [true, false].map(value => <label key={String(value)}><input type="radio" name={q.id} checked={answers[q.id]?.value === value} onChange={() => onChange(q.id, { value })} />{t(`elearning.assessment.${value ? "true" : "false"}`)}</label>)}
    {["matching", "listen_match"].includes(q.type) && q.config.prompts.map((prompt, i) => <div className="assessment-pair" key={prompt.id}>
      {q.type === "listen_match" ? <MediaBlockRenderer kind="audio" block={{ title: `${t("elearning.content.types.audio")} ${i + 1}`, media: prompt.media }} /> : <p>{prompt.label}</p>}
      <label>{q.type === "listen_match" ? `${t("elearning.content.types.audio")} ${i + 1}` : prompt.label}<select required value={answers[q.id]?.matches?.[prompt.id] || ""} onChange={event => onChange(q.id, { matches: { ...answers[q.id]?.matches, [prompt.id]: event.target.value } })}><option value="">{t("elearning.assessment.select")}</option>{q.config.targets.map(target => <option key={target.id} value={target.id}>{target.label}</option>)}</select></label>
    </div>)}
  </fieldset>);
}
