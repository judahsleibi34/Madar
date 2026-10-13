import LearningErrorNotice from "./LearningErrorNotice";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { learningFormsApi } from "./learningFormsApi";
import { getLocalizedValue } from "../PageBuilder/core/PageBuilder.localization";
import { SubmissionAnswer } from "./LearningFormSubmissionTables";
export default function LearningFormApplicantResponse() {
  const {responseId}=useParams();const {t,i18n}=useTranslation("dashboard");
  const [state,setState]=useState({loading:true}),[retry,setRetry]=useState(0);
  useEffect(()=>{let active=true;learningFormsApi(`/my-responses/${responseId}`).then(data=>{if(active)setState({data});}).catch(()=>{if(active)setState({error:true});});return()=>{active=false;};},[responseId,retry]);
  const language=i18n.language.startsWith("ar")?"ar":"en";
  if(state.loading)return <p role="status">{t("elearning.forms.loading")}</p>;
  if(state.error)return <div><LearningErrorNotice as="p">{t("elearning.forms.error")}</LearningErrorNotice><button type="button" onClick={()=>setRetry(value=>value+1)}>{t("elearning.retry")}</button></div>;
  const data=state.data;
  return <section className="elearning-owner-page" dir={i18n.dir()}><Link to="/my-learning/dashboard">{t("sidebar.dashboard")}</Link>
    <h1>{getLocalizedValue(data.schema,"title",language)}</h1><p role="status">{t(`elearning.programmes.${data.status}`)}</p>
    <p>{new Date(data.submitted_at).toLocaleString(i18n.language)}</p>
    <table><caption>{t("elearning.forms_review.your_answers")}</caption><thead><tr><th>{t("elearning.forms_review.question")}</th><th>{t("elearning.forms_review.answer")}</th></tr></thead><tbody>
      {data.schema.sections.flatMap(section=>section.fields).filter(field=>field.type!=="file" && Object.hasOwn(data.answers,field.id)).map(field=><tr key={field.id}><th scope="row">{getLocalizedValue(field,"label",language)}</th><td><SubmissionAnswer value={data.answers[field.id]} field={field} /></td></tr>)}
    </tbody></table>
  </section>;
}
