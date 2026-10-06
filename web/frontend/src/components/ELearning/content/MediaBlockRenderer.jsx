import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import LoadingBar from "../../common/LoadingBar";
import { getApiUrl } from "../../../utils/apiClient";

export default function MediaBlockRenderer({ block, kind }) {
  const { t } = useTranslation("dashboard");
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);
  const mediaRef = useRef(null);
  const Tag = kind;
  // Only managed URLs supplied by the backend are rendered. No arbitrary embeds.
  const url = block.media?.url;
  if (!url || !/^\/uploads\/tenant_[1-9][0-9]*\/builder_assets\/[a-f0-9]{32}\.(mp3|wav|mp4|webm)$/.test(url)) {
    return <p role="alert">{t("elearning.content.mediaError")}</p>;
  }
  return <div className="elearning-media-content">
    {loading && <LoadingBar mode="inline" label={t("elearning.content.loadingMedia")} />}
    <Tag ref={mediaRef} key={url} controls preload="metadata" src={getApiUrl(url)} aria-label={block.title || block.media.filename} onError={() => { setFailed(true); setLoading(false); }} onLoadedMetadata={() => { setFailed(false); setLoading(false); }} />
    {failed && <p role="alert">{t("elearning.content.mediaError")} <button className="ecommerce-secondary-button" type="button" onClick={() => { setFailed(false); setLoading(true); mediaRef.current?.load(); }}>{t("elearning.retry")}</button></p>}
    {block.media.filename && <small>{block.media.filename}</small>}
    {block.content?.caption && <p>{block.content.caption}</p>}
  </div>;
}
