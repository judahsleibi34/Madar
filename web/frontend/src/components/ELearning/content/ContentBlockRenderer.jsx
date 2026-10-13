import { useTranslation } from "react-i18next";
import TextBlockRenderer from "./TextBlockRenderer";
import MediaBlockRenderer from "./MediaBlockRenderer";

import AssessmentBlockRenderer from "./AssessmentBlockRenderer";
import { useLearningExperience } from "../LearningExperienceContext";

const renderers = {
  assessment: AssessmentBlockRenderer,
  text: ({ block, card }) => <TextBlockRenderer content={block.content} title={card ? block.title : undefined} />,
  audio: ({ block }) => <MediaBlockRenderer key={block.media_id || block.media?.url} block={block} kind="audio" />,
  video: ({ block }) => <MediaBlockRenderer key={block.media_id || block.media?.url} block={block} kind="video" />,
};
export default function ContentBlockRenderer({ block, context = "author", courseId, lessonId, onAssessmentChange }) {
  const { t } = useTranslation("dashboard");
  const Renderer = renderers[block.type];
  // Structured lesson cards carry their own heading (opt-in academies only).
  const card = useLearningExperience().lessonComponents === true && block.type === "text" && Boolean(block.content?.component);
  if (block.archived_at) return null;
  return <section className="elearning-content-renderer">
    {block.title && block.type !== "assessment" && !card && <h3>{block.title}</h3>}
    {Renderer ? <Renderer block={block} card={card} context={context} courseId={courseId} lessonId={lessonId} onAssessmentChange={onAssessmentChange} /> : <p>{t("elearning.content.unsupported")}</p>}
  </section>;
}
