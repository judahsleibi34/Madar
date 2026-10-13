import { useContext, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Award, Lock } from "lucide-react";
import { fetchCertificates } from "../../../services/elearningCredentials";
import ELearningSkeleton from "../ELearningSkeleton";
import ExamCard from "../content/ExamCard";
import useStudentData from "./useStudentData";
import { StudentDataContext } from "./StudentDataContext";
import { StatusPill, StudentPage } from "./StudentParts";

// Book document §29–31: exact certificate names.
const CERTIFICATES = [["A1", "A1 English Speaking Certificate"], ["A2", "A2 English Speaking Certificate"], ["B1", "B1 English Speaking Certificate"],
  ["B2", "B2 English Speaking Certificate"], ["C1", "C1 English Speaking Certificate"], ["course", "Complete English Speaking Course Certificate"]];

/** EH / Exams & Certificates: exam cards and the six certificates (earned or locked). */
export default function StudentExams() {
  const { t, i18n } = useTranslation("dashboard");
  const data = useStudentData();
  const sample = useContext(StudentDataContext);
  const [loaded, setCredentials] = useState(null);
  const credentials = sample?.credentials || loaded;
  useEffect(() => { if (sample) return undefined; let active = true; fetchCertificates().then(value => { if (active) setCredentials(value.credentials || []); }).catch(() => { if (active) setCredentials([]); }); return () => { active = false; }; }, [sample]);
  if (data.loading || credentials === null) return <ELearningSkeleton label={t("elearning.loading")} direction={i18n.dir()} />;
  const courseId = data.enrolled?.course?.id, exams = data.course?.assessments || [];
  const earned = key => credentials.find(row => row.status !== "revoked" && (key === "course" ? !row.snapshot?.cefr_level : row.snapshot?.cefr_level === key));
  return <StudentPage title={t("elearning.student.examsCertificates")} intro={t("elearning.student.examsIntro")}>
    <h2>{t("elearning.student.exams")}</h2>
    {exams.length ? <div className="exam-card-list">{exams.map(exam => <ExamCard key={exam.placement_id} exam={exam} href={courseId ? `/my-learning/courses/${courseId}/assessments/${exam.placement_id}` : undefined} />)}</div> : <p className="student-empty">{t("elearning.student.noExams")}</p>}
    <h2>{t("elearning.student.certificates")}</h2>
    <div className="certificate-card-grid">
      {CERTIFICATES.map(([key, name]) => { const row = earned(key); return <article key={key} className={`certificate-card ${row ? "is-earned" : "is-locked"}`}>
        {row ? <Award size={28} aria-hidden="true" /> : <Lock size={28} aria-hidden="true" />}
        <h3 lang="en">{name}</h3>
        <StatusPill status={row ? "earned" : "locked"}>{t(row ? "elearning.student.certificateEarned" : "elearning.student.certificateLocked")}</StatusPill>
        {row?.final_score != null && <span>{t("elearning.certificates.finalScore")}: {row.final_score}%</span>}
        {row && <Link to={`/my-learning/certificates/${row.id}`}>{t("elearning.certificates.viewCertificate")}</Link>}
      </article>; })}
    </div>
  </StudentPage>;
}
