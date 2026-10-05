/* eslint-disable react-refresh/only-export-components -- Builder composition context */
import { createContext, useContext } from "react";
import { Link } from "react-router-dom";
import { getBrandedMadarSubdomain } from "../../../utils/hostedAddress";
import { useTranslation } from "react-i18next";
export const AcademyCompositionContext = createContext(null);
export default function AcademyDataBlock({ element, editing = false }) {
  const runtime = useContext(AcademyCompositionContext);
  const { t } = useTranslation("dashboard");
  const config = element.academy || {};
  const heading = config.heading || element.name;
  const setupKeys = { academyFeaturedCourses: "featured", academyCourseCollection: "courses", academyPlans: "plans", academyInstructors: "instructors", academyContinueLearning: "continue" };
  const empty = (key = setupKeys[element.type]) => editing ? <section className="academy-section academy-builder-empty" data-academy-component={element.type}>
    <h2>{heading}</h2>{config.description && <p>{config.description}</p>}
    <p role={key === "loading" ? "status" : key === "error" ? "alert" : undefined}>{t(`elearning.academy.builderData.${key}`)}</p>
    {key === "error" && runtime?.refresh && <button type="button" onClick={runtime.refresh}>{t("elearning.retry")}</button>}
  </section> : null;
  if (!runtime) return empty("unavailable");
  if (!runtime.data) return empty(runtime.loading ? "loading" : "error");
  const { data, renderCollection, renderPlans } = runtime;
  const maximum = Math.max(1, Math.min(24, config.maxItems || 4));
  if (element.type === "academyContinueLearning") {
    if (!data.authenticated || !data.continue_courses?.length) return empty();
    return <div data-academy-component={element.type} className={`academy-data-variant-${config.variant || "grid"}`}>{renderCollection(heading, (data.continue_courses || []).slice(0, maximum))}</div>;
  }
  if (element.type === "academyInstructors") {
    const instructors = (data.instructors || []).filter(item => !config.instructorIds?.length || config.instructorIds.includes(item.id)).slice(0, maximum);
    return instructors.length ? <section data-academy-component={element.type} className={`academy-section academy-data-variant-${config.variant || "grid"}`}><h2>{heading}</h2>{config.description && <p>{config.description}</p>}<div className="academy-grid">{instructors.map(item => <article className="academy-card" key={item.id}><div className="academy-card-body"><h3>{item.name}</h3>{item.description && <p>{item.description}</p>}{data.courses.filter(course => item.course_ids.includes(course.id)).map(course => <Link key={course.id} to={`${getBrandedMadarSubdomain(window.location.hostname) ? "/academy" : `/academy/${data.site.subdomain}`}/courses/${course.id}`}>{course.name}</Link>)}</div></article>)}</div></section> : empty();
  }
  if (element.type === "academyPlans") {
    const plans = data.plans.filter(plan => !config.planIds?.length || config.planIds.includes(plan.id)).slice(0, maximum);
    return plans.length ? <section data-academy-component={element.type} className={`academy-section academy-data-variant-${config.variant || "grid"}`}><h2>{heading}</h2>{config.description && <p>{config.description}</p>}{renderPlans(plans)}</section> : empty();
  }
  const courses = data.courses.filter(course =>
    (!config.courseIds?.length || config.courseIds.includes(course.id)) &&
    (!(config.featuredOnly || (element.type === "academyFeaturedCourses" && !config.courseIds?.length)) || course.featured)
  ).slice(0, maximum);
  return courses.length ? <div data-academy-component={element.type} className={`academy-data-variant-${config.variant || "grid"}`}>{config.description && <p>{config.description}</p>}{renderCollection(heading, courses)}</div> : empty();
}
