import { useTranslation } from "react-i18next";
import { BookOpenText, Check, Lightbulb, MapPin, MessageSquareQuote, X } from "lucide-react";
import "../../../styles/lesson-components.css";

// English learning content stays English (LTR) inside Arabic pages; Arabic
// support text is marked Arabic (RTL) inside English pages.
const En = ({ as: Tag = "span", children, ...props }) => <Tag lang="en" dir="ltr" {...props}>{children}</Tag>;
const Ar = ({ as: Tag = "span", children, ...props }) => <Tag lang="ar" dir="rtl" {...props}>{children}</Tag>;

function CardHeader({ icon: Icon, title }) {
  return <header className="lesson-card-header"><Icon size={22} aria-hidden="true" /><h3>{title}</h3></header>;
}

/** EH / Vocabulary Card: word, simple English meaning, Arabic meaning, example, pronunciation. */
export function VocabularyCard({ title, items }) {
  const { t } = useTranslation("dashboard");
  return <section className="lesson-card lesson-vocabulary">
    <CardHeader icon={BookOpenText} title={title || t("elearning.lessonCards.vocabulary")} />
    <ul className="lesson-vocabulary-list">
      {items.map((item, index) => <li key={`${item.word}-${index}`} className="lesson-vocabulary-item">
        <En as="strong" className="lesson-vocabulary-word">{item.word}</En>
        {(item.pronunciation || item.stress) && <p className="lesson-vocabulary-sound">
          {item.pronunciation && <><span className="lesson-card-label">{t("elearning.lessonCards.pronunciation")}</span> <En>{item.pronunciation}</En></>}
          {item.stress && <>{item.pronunciation ? " · " : ""}<span className="lesson-card-label">{t("elearning.lessonCards.stress")}</span> <En>{item.stress}</En></>}
        </p>}
        <p><span className="lesson-card-label">{t("elearning.lessonCards.meaning")}</span> <En>{item.meaning}</En></p>
        {item.arabic && <p><span className="lesson-card-label">{t("elearning.lessonCards.arabic")}</span> <Ar>{item.arabic}</Ar></p>}
        {item.example && <En as="p" className="lesson-card-example">{item.example}</En>}
      </li>)}
    </ul>
  </section>;
}

/** EH / Expression Card: useful expressions with meaning, Arabic and an example. */
export function ExpressionCard({ title, items }) {
  const { t } = useTranslation("dashboard");
  return <section className="lesson-card lesson-expressions">
    <CardHeader icon={MessageSquareQuote} title={title || t("elearning.lessonCards.expressions")} />
    <ul className="lesson-expression-list">
      {items.map((item, index) => <li key={`${item.expression}-${index}`}>
        <En as="strong" className="lesson-expression">“{item.expression}”</En>
        {item.meaning && <p><span className="lesson-card-label">{t("elearning.lessonCards.meaning")}</span> <En>{item.meaning}</En></p>}
        {item.arabic && <p><span className="lesson-card-label">{t("elearning.lessonCards.arabic")}</span> <Ar>{item.arabic}</Ar></p>}
        {item.example && <En as="p" className="lesson-card-example">{item.example}</En>}
      </li>)}
    </ul>
  </section>;
}

/** EH / Arabic Speaker Tip: a common difficulty, with what to avoid and what to say. */
export function SpeakerTip({ title, tip, arabic, avoid, say }) {
  const { t } = useTranslation("dashboard");
  return <aside className="lesson-card lesson-speaker-tip">
    <CardHeader icon={Lightbulb} title={title || t("elearning.lessonCards.speakerTip")} />
    <En as="p">{tip}</En>
    {arabic && <Ar as="p">{arabic}</Ar>}
    {(avoid || say) && <div className="lesson-speaker-compare">
      {avoid && <p className="is-avoid"><X size={18} aria-hidden="true" /><span className="lesson-card-label">{t("elearning.lessonCards.avoid")}</span> <En>{avoid}</En></p>}
      {say && <p className="is-say"><Check size={18} aria-hidden="true" /><span className="lesson-card-label">{t("elearning.lessonCards.say")}</span> <En>{say}</En></p>}
    </div>}
  </aside>;
}

/** EH / Real-Life Situation: the topic's situation, in English. */
export function SituationCard({ title, text }) {
  const { t } = useTranslation("dashboard");
  return <section className="lesson-card lesson-situation">
    <CardHeader icon={MapPin} title={title || t("elearning.lessonCards.situation")} />
    <En as="p">{text}</En>
  </section>;
}

export default function LessonComponentCard({ title, component }) {
  if (component.kind === "vocabulary") return <VocabularyCard title={title} items={component.items} />;
  if (component.kind === "expressions") return <ExpressionCard title={title} items={component.items} />;
  if (component.kind === "speaker_tip") return <SpeakerTip title={title} {...component} />;
  if (component.kind === "situation") return <SituationCard title={title} text={component.text} />;
  return null;
}
