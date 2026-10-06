import { useTranslation } from "react-i18next";
import TextBlockRenderer from "./TextBlockRenderer";
import MediaBlockRenderer from "./MediaBlockRenderer";

import AssessmentBlockRenderer from "./AssessmentBlockRenderer";

const renderers = {
  assessment: AssessmentBlockRenderer,
  text: ({ block }) => <TextBlockRenderer content={block.content} />,
  audio: ({ block }) => <MediaBlockRenderer key={block.media_id || block.media?.url} block={block} kind="audio" />,
  video: ({ block }) => <MediaBlockRenderer key={block.media_id || block.media?.url} block={block} kind="video" />,
};
export default function ContentBlockRenderer({ block, context = "author", courseId, lessonId, onAssessmentChange }) {
  const { t } = useTranslation("dashboard");
  const Renderer = renderers[block.type];
  if (block.archived_at) return null;
  return <section className="elearning-content-renderer">
    {block.title && block.type !== "assessment" && <h3>{block.title}</h3>}
    {Renderer ? <Renderer block={block} context={context} courseId={courseId} lessonId={lessonId} onAssessmentChange={onAssessmentChange} /> : <p>{t("elearning.content.unsupported")}</p>}
  </section>;
}
