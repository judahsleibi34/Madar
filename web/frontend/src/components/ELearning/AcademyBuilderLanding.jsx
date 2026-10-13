import LearningErrorNotice from "./LearningErrorNotice";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import useAcademySiteChrome from "./useAcademySiteChrome";
import { resolveStrictPublishedPageByPath, getPublicPagePath } from "../PageBuilder/core/PageBuilder.routing";
import { getPageBuilderThemeVars } from "../PageBuilder/core/PageBuilder.theme";
import SiteRenderer from "../PageBuilder/core/PageBuilder.siteRenderer";
import { createElementRenderer } from "../PageBuilder/core/PageBuilder.elementRenderer";
import { carouselElementTypes } from "../PageBuilder/core/PageBuilder.config";
import { ACADEMY_COMPONENT_TYPES } from "../PageBuilder/core/PageBuilder.academyProfile";
import { getBuilderElementStyle } from "../PageBuilder/core/PageBuilder.styles";
import { getElementPlacementMargins, getElementLayoutWidth, normalizeElementAlignSelf } from "../PageBuilder/core/PageBuilder.elementLayout";
import { getLiveArtboardProfile } from "../PageBuilder/core/PageBuilder.artboard";
import { runPublicElementAction } from "../PageBuilder/core/PageBuilder.actions";
import { getStoredUrlError } from "../PageBuilder/core/PageBuilder.url";
import { localizePresentation } from "../PageBuilder/core/PageBuilder.presentationLocalization";
import "../../styles/admin/PageBuilder/index.css";

export default function AcademyBuilderLanding({ schema: sourceSchema, basePath = "", authenticated = false, registration }) {
  const { t, i18n } = useTranslation("dashboard");
  const language=i18n.language.startsWith("ar") ? "ar" : "en";
  const schema = useMemo(()=>localizePresentation(sourceSchema,language),[sourceSchema,language]);
  const navigate = useNavigate();
  const params = useParams();
  const activePage = resolveStrictPublishedPageByPath(schema?.pages, `/${params["*"] || ""}`, schema?.defaultPageId);
  const selectPage = id => { const page = schema?.pages.find(page => page.id === id); if (page) navigate(getPublicPagePath(basePath, page)); };
  const [width, setWidth] = useState(window.innerWidth);
  const containerRef = useRef(null);
  useEffect(() => {
    const resize = () => setWidth(containerRef.current?.clientWidth || window.innerWidth);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(resize);
    if (containerRef.current) observer?.observe(containerRef.current);
    resize(); window.addEventListener("resize", resize);
    return () => { observer?.disconnect(); window.removeEventListener("resize", resize); };
  }, [schema]);
  const profile = getLiveArtboardProfile(width);
  const elementStyle = element => getBuilderElementStyle({ element: { ...element, styles: element.styles || {} }, selected: { type: "", id: "" }, carouselElementTypes, getElementPlacementMargins, getElementLayoutWidth, normalizeElementAlignSelf });
  const renderElement = createElementRenderer({
    selected: { type: "", id: "" }, preview: true, renderMode: "runtime", carouselElementTypes,
    getFreeElementStyle: elementStyle, getElementStyle: elementStyle,
    startDrag: () => {},
    runElementAction: element => runPublicElementAction({ element, pages: schema?.pages || [], getStoredUrlError, allowRelative: true,
      goToPage: page => selectPage(page.id),
      openExternal: url => { const target = new URL(url, window.location.origin); if (target.origin === window.location.origin) navigate(target.pathname + target.search + target.hash); else window.location.assign(target.href); },
    }),
  });
  const { renderSiteHeader, renderSiteFooter } = useAcademySiteChrome({ schema, basePath, authenticated, registration, activePage });
  if (!schema) return null;
  if (!activePage) return <LearningErrorNotice as="p">{t("elearning.academy.pageNotFound")}</LearningErrorNotice>;
  return <div ref={containerRef} dir="ltr" className={`academy-landing-region tenant-runtime-page${schema.name === "Madar Learning" ? " madar-learning-landing" : ""}`} style={getPageBuilderThemeVars(schema.theme)}><SiteRenderer project={schema} activePage={activePage} {...profile} canvasStyle={{ direction: i18n.dir() }} availablePresentationWidth={width} expandToAvailableWidth renderElement={renderElement} carouselElementTypes={carouselElementTypes} filterElement={element => ACADEMY_COMPONENT_TYPES.has(element.type)} renderSiteHeader={renderSiteHeader} renderSiteFooter={renderSiteFooter} className="academy-builder-landing" getSectionProps={section => ({ "data-landing-section": section.id })} /></div>;
}
