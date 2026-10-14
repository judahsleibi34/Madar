import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import ELearningSkeleton from "../ELearningSkeleton";
import LearningErrorNotice from "../LearningErrorNotice";
import useStudentData from "./useStudentData";
import { StatusPill, StudentPage } from "./StudentParts";
import { TuitionProgress } from "./StudentReferral";

const latest = (rows, kind) => rows.filter(row => row.kind === kind).sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];

function ApplicationStatus({ row }) {
  const { t, i18n } = useTranslation("dashboard");
  return <p className="application-status"><StatusPill status={row.status}>{t(`elearning.programmes.${row.status}`)}</StatusPill>
    <span>{t("elearning.student.submittedOn", { date: new Date(row.created_at).toLocaleDateString(i18n.language) })}</span></p>;
}

/** EH / Applications (website document §17): Tuition Support and Exchange, clearly separate. */
export default function StudentApplications() {
  const { t, i18n } = useTranslation("dashboard");
  const data = useStudentData({ withCourse: false });
  if (data.loading) return <ELearningSkeleton label={t("elearning.loading")} direction={i18n.dir()} />;
  const account = data.programmes;
  if (!account) return <StudentPage title={t("elearning.student.applications")}><LearningErrorNotice as="p">{t("elearning.player.unavailable")}</LearningErrorNotice></StudentPage>;
  const rows = account.applications || [], paths = account.application_paths || {}, settings = account.settings || {};
  const wallet = account.wallet || account.eligibility;
  const tuition = latest(rows, "tuition"), exchange = latest(rows, "exchange");
  const tuitionOn = account.capabilities?.tuition && settings.tuition_support_enabled;
  const exchangeOn = account.capabilities?.exchange && settings.exchange_programme_enabled;
  const reapply = row => !row || row.status === "not_approved";
  return <StudentPage title={t("elearning.student.applications")}>
    {tuitionOn && <div className="application-block" data-testid="application-tuition">
      <TuitionProgress wallet={wallet} title={settings.support_programme_name}>
        {tuition && <ApplicationStatus row={tuition} />}
        {reapply(tuition) && (wallet?.tuition_eligible
          ? <Link className="ecommerce-primary-button" to={paths.tuition || "/my-learning/programmes?kind=tuition"}>{t("elearning.student.applyNow")}</Link>
          : <button type="button" className="ecommerce-primary-button" disabled>{t("elearning.student.applyNow")}</button>)}
        <small>{t("elearning.student.tuitionNotGuaranteed")}</small>
      </TuitionProgress>
    </div>}
    {exchangeOn && <section className="student-panel application-block" data-testid="application-exchange">
      <h2>{settings.exchange_programme_name || t("elearning.student.exchangeProgramme")}</h2>
      <p>{t("elearning.student.exchangeHelp")}</p>
      {exchange && <ApplicationStatus row={exchange} />}
      {reapply(exchange) && <Link className="ecommerce-primary-button" to={paths.exchange || "/my-learning/exchange"}>{t("elearning.student.applyExchange")}</Link>}
    </section>}
    {!tuitionOn && !exchangeOn && <p className="student-empty">{t("elearning.player.unavailable")}</p>}
  </StudentPage>;
}
