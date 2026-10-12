import { getResponsiveMediaProps } from "../../../utils/media";
import { useTranslation } from "react-i18next";
import "../../../styles/education-hero.css";

export default function EducationHero({ element, onAction, editing = false }) {
  const focal=value=>value!=null && Number.isFinite(Number(value)) ? Math.max(0,Math.min(100,Number(value))) : 50;
  const {i18n}=useTranslation();
  const media = getResponsiveMediaProps(element.imageUrl, {widths:[640,960,1440,1920],fallbackWidth:1440,sizes:"100vw"});
  return <section dir={i18n.dir()} className="builder-education-hero" aria-label={element.title || element.content}>
    {media.src && <img {...media} className="builder-education-hero-image" alt={element.alt || ""}
      fetchPriority="high" style={{objectPosition:`${focal(element.focalX)}% ${focal(element.focalY)}%`}} />}
    <div className="builder-education-hero-overlay" aria-hidden="true" />
    <div className="builder-education-hero-copy">
      {element.eyebrow && <p className="builder-education-hero-eyebrow">{element.eyebrow}</p>}
      <h1>{element.content}</h1><p>{element.description}</p>
      <div className="builder-education-hero-actions">
        {[{label:element.primaryLabel,action:element.action},{label:element.secondaryLabel,action:element.secondaryAction}]
          .filter(item => item.label).map((item,index) => <button type="button" key={index}
            className={index ? "is-secondary" : "is-primary"} disabled={editing}
            onClick={() => onAction?.({...element,type:"button",action:item.action})}>{item.label}</button>)}
      </div>
      {element.caption && <small>{element.caption}</small>}
    </div>
  </section>;
}
