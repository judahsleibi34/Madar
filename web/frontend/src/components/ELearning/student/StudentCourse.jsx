import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { CheckCircle2, Circle, CircleDot, Lock } from "lucide-react";
import { courseLevels, currentLevel } from "../../../utils/studentLevels";
import { academyPath } from "../AcademyNav";
import ELearningSkeleton from "../ELearningSkeleton";
import LearningErrorNotice from "../LearningErrorNotice";
import ExamCard from "../content/ExamCard";
import useStudentData from "./useStudentData";
import { LevelCard, ProgressBar, StudentPage } from "./StudentParts";

/** EH / My Course (website document §15): 10 Levels with progress, and Level detail. */
export default function StudentCourse() {
  const { t, i18n } = useTranslation("dashboard");
  const { sectionId } = useParams();
  const data = useStudentData();
  if (data.loading) return <ELearningSkeleton label={t("elearning.loading")} direction={i18n.dir()} />;
  if (data.error) return <LearningErrorNotice as="p">{t("elearning.player.loadError")} <button onClick={data.retry}>{t("elearning.retry")}</button></LearningErrorNotice>;
  if (!data.enrolled) {
    const academy = data.learning?.academy;
    return <StudentPage title={t("elearning.student.myCourse")}>
      <div className="student-empty"><p>{t("elearning.student.notEnrolled")}</p>{academy && <Link className="ecommerce-primary-button" to={`${academyPath(academy)}/courses`}>{t("elearning.student.enrollNow")}</Link>}</div>
    </StudentPage>;
  }
  const courseId = data.enrolled.course.id, levels = courseLevels(data.course), level = currentLevel(levels);
  const progress = Math.round(Number(data.enrolled.progress?.progress_percent) || 0);
  const selected = sectionId ? levels.find(item => item.id === sectionId) : null;
  if (selected) {
    const exams = (data.course?.assessments || []).filter(exam => exam.section_id === selected.id);
    return <StudentPage title={t("elearning.student.levelTitle", { number: selected.number, title: String(selected.name).replace(/^Level\s+\d+\s*[—-]\s*/i, "") })} intro={selected.cefr}>
      <Link to="/my-learning/course">{t("elearning.student.allLevels")}</Link>
      <ProgressBar value={selected.progress_percent || 0} label={t("elearning.student.levelProgress")} />
      <ol className="topic-row-list">
        {selected.lessons.map((lesson, index) => {
          const status = lesson.completed ? "completed" : lesson.locked ? "locked" : lesson.id === data.course?.continue_lesson_id ? "current" : "available";
          const Icon = { completed: CheckCircle2, locked: Lock, current: CircleDot, available: Circle }[status];
          const name = <><span className="topic-row-number">{index + 1}</span><span lang="en">{lesson.name}</span></>;
          return <li key={lesson.id} className={`topic-row is-${status}`}>
            {status === "locked" ? <span className="topic-row-link">{name}</span> : <Link className="topic-row-link" to={`/my-learning/courses/${courseId}/lessons/${lesson.id}`}>{name}</Link>}
            <span className={`topic-row-status is-${status}`}><Icon size={16} aria-hidden="true" />{t(`elearning.topicStatus.${status}`)}</span>
          </li>;
        })}
      </ol>
      {exams.length > 0 && <div className="exam-card-list">{exams.map(exam => <ExamCard key={exam.placement_id} exam={exam} href={`/my-learning/courses/${courseId}/assessments/${exam.placement_id}`} />)}</div>}
    </StudentPage>;
  }
  return <StudentPage title={data.enrolled.course.name}>
    <div className="course-summary">
      <strong>{level ? t("elearning.student.levelOf", { number: level.number, total: levels.length }) : ""}</strong>
      <span>{t("elearning.student.courseProgress", { percent: progress })}</span>
      <ProgressBar value={progress} label={t("elearning.student.overallProgress")} />
      <span>{t("elearning.student.levelsSummary", { completed: levels.filter(item => item.state === "completed").length, remaining: levels.filter(item => item.state !== "completed").length })}</span>
      <Link className="ecommerce-primary-button" to={data.course?.continue_lesson_id ? `/my-learning/courses/${courseId}/lessons/${data.course.continue_lesson_id}` : `/my-learning/courses/${courseId}`}>{t("elearning.player.continue")}</Link>
    </div>
    <div className="level-path">{levels.map(item => <LevelCard key={item.id} level={item} to={`/my-learning/course/levels/${item.id}`} />)}</div>
  </StudentPage>;
}
