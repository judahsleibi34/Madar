import LearningErrorNotice from "./LearningErrorNotice";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { learningFormsApi } from "./learningFormsApi";
import { getLocalizedValue } from "../PageBuilder/core/PageBuilder.localization";

export default function LearningFormApplicantResponses() {
  const {t,i18n}=useTranslation("dashboard");
  const [page,setPage]=useState(0),[retry,setRetry]=useState(0),[state,setState]=useState({loading:true});
  useEffect(()=>{
    let active=true;
    learningFormsApi(`/my-responses?limit=25&offset=${page*25}`).then(data=>{if(active)setState({data,page});}).catch(()=>{if(active)setState({error:true,page});});
    return()=>{active=false;};
  },[page,retry]);
  const label=key=>t(`elearning.forms.${key}`);
  return <section className="learner-account" dir={i18n.dir()}>
    <h1>{t("elearning.forms_review.my_submissions")}</h1>
    {(state.loading || state.page!==page) ? <p role="status">{label("loading")}</p> : state.error ? <LearningErrorNotice as="p">{label("error")} <button onClick={()=>setRetry(value=>value+1)}>{t("elearning.retry")}</button></LearningErrorNotice> : <>
      <table className="learner-data-table"><thead><tr><th>{label("title")}</th><th>{t("elearning.owner.status")}</th><th>{t("elearning.ui.submitted")}</th></tr></thead><tbody>
        {state.data.items.map(row=><tr key={row.id}><td><Link to={`/my-learning/form-responses/${row.id}`}>{getLocalizedValue(row,"title",i18n.language.startsWith("ar")?"ar":"en")}</Link></td><td>{t(`elearning.programmes.${row.status}`)}</td><td>{new Date(row.submitted_at).toLocaleString(i18n.language)}</td></tr>)}
      </tbody></table>
      {!state.data.items.length && <p>{t("elearning.programmes.empty")}</p>}
      <button disabled={!page} onClick={()=>setPage(value=>value-1)}>{t("elearning.programmes.previous")}</button>
      <button disabled={!state.data.has_more} onClick={()=>setPage(value=>value+1)}>{t("elearning.programmes.next")}</button>
    </>}
  </section>;
}
