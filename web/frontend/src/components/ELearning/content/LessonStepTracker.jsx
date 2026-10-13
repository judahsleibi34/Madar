import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Circle, CircleDot } from "lucide-react";
import { stepAnchor } from "../../../utils/lessonSteps";
import "../../../styles/lesson-components.css";

/**
 * EH / Lesson Step Tracker: the book's topic steps present in this lesson.
 * A step is Completed when its required checks are passed or the learner has
 * read past it, Current while it is on screen, otherwise Next.
 */
export default function LessonStepTracker({ steps, passedSteps = [] }) {
  const { t } = useTranslation("dashboard");
  const [current, setCurrent] = useState(steps[0]?.step), [visited, setVisited] = useState(() => new Set());
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return undefined;
    const observer = new IntersectionObserver(entries => {
      const visible = entries.filter(entry => entry.isIntersecting).map(entry => entry.target.dataset.step);
      if (!visible.length) return;
      setCurrent(visible[0]);
      setVisited(previous => {
        const order = steps.map(item => item.step), reached = Math.max(...visible.map(step => order.indexOf(step)));
        return new Set([...previous, ...order.slice(0, reached)]);
      });
    }, { rootMargin: "-20% 0px -60% 0px" });
    steps.forEach(({ step }) => { const node = document.getElementById(stepAnchor(step)); if (node) observer.observe(node); });
    return () => observer.disconnect();
  }, [steps]);
  return <nav className="lesson-step-tracker" aria-label={t("elearning.lessonSteps.label")}>
    <ol>
      {steps.map(({ step }, index) => {
        const done = passedSteps.includes(step) || (visited.has(step) && step !== current);
        const status = done ? "completed" : step === current ? "current" : "next";
        const Icon = status === "completed" ? CheckCircle2 : status === "current" ? CircleDot : Circle;
        return <li key={step} className={`is-${status}`}>
          <a href={`#${stepAnchor(step)}`} aria-current={status === "current" ? "step" : undefined}>
            <span className="lesson-step-number" aria-hidden="true">{index + 1}</span>
            <span className="lesson-step-name">{t(`elearning.lessonSteps.${step}`)}</span>
            <span className="lesson-step-status"><Icon size={15} aria-hidden="true" />{t(`elearning.lessonSteps.status_${status}`)}</span>
          </a>
        </li>;
      })}
    </ol>
  </nav>;
}
