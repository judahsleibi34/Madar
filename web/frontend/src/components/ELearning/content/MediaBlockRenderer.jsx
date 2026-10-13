import LearningErrorNotice from "../LearningErrorNotice";
import { useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import LoadingBar from "../../common/LoadingBar";
import { getApiUrl } from "../../../utils/apiClient";

export default function MediaBlockRenderer({ block, kind }) {
  const { t } = useTranslation("dashboard");
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const mediaRef = useRef(null);
  const transcriptId = useId();
  const [transcriptVisible, setTranscriptVisible] = useState(false);
  const Tag = kind;
  // Only managed URLs supplied by the backend are rendered. No arbitrary embeds.
  const url = block.media?.url;
  if (!url || !/^\/uploads\/tenant_[1-9][0-9]*\/builder_assets\/[a-f0-9]{32}\.(mp3|wav|mp4|webm)$/.test(url)) {
    return <LearningErrorNotice as="p">{t("elearning.content.mediaError")}</LearningErrorNotice>;
  }
  return <div className="elearning-media-content">
    {loading && <LoadingBar mode="inline" label={t("elearning.content.loadingMedia")} />}
    <Tag ref={mediaRef} key={url} controls preload="metadata" src={getApiUrl(url)} aria-label={block.title || block.media.filename} onError={() => { setFailed(true); setLoading(false); }} onLoadedMetadata={() => { setFailed(false); setLoading(false); }} />
    {failed && <LearningErrorNotice as="p">{t("elearning.content.mediaError")} <button className="ecommerce-secondary-button" type="button" onClick={() => { setFailed(false); setLoading(true); mediaRef.current?.load(); }}>{t("elearning.retry")}</button></LearningErrorNotice>}
    {block.media.filename && <small>{block.media.filename}</small>}
    {block.content?.caption && <p>{block.content.caption}</p>}
    {kind === "audio" && block.content?.transcript && <div>
      <button type="button" className="ecommerce-secondary-button" aria-expanded={transcriptVisible} aria-controls={transcriptId} onClick={() => setTranscriptVisible(value => !value)}>{t(`elearning.content.${transcriptVisible ? "hideTranscript" : "showTranscript"}`)}</button>
      <p id={transcriptId} hidden={!transcriptVisible} style={{ whiteSpace: "pre-wrap" }}>{block.content.transcript}</p>
    </div>}
  </div>;
}
