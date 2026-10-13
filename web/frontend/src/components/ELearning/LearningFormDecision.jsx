import LearningErrorNotice from "./LearningErrorNotice";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { learningFormsApi } from "./learningFormsApi";
import { OwnerStatus, OwnerTable } from "./OwnerUI";

export default function LearningFormDecision({ response, onChanged }) {
  const { t, i18n }=useTranslation("dashboard");
  const decision=response.review;
  const kind=response.definition.schema.workflow?.kind || "none";
  const options=decision.status === "approved" && kind === "affiliate" ? ["suspended"]
    : decision.status === "suspended" && kind === "affiliate" ? ["approved"]
      : ["submitted","under_review"].includes(decision.status) ? ["under_review","approved","not_approved"].filter(value=>value!==decision.status) : [];
  const [status,setStatus]=useState(options[0] || ""),[note,setNote]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState(false);
  const copy=key=>t(`elearning.forms_review.${key}`);
  async function save(event) {
    event.preventDefault();if(busy)return;setBusy(true);setError(false);
    try {await learningFormsApi(`/responses/${response.id}/decision`,{method:"POST",body:{status,note,revision:decision.revision}});onChanged();}
    catch {setError(true);}finally {setBusy(false);}
  }
  return <section className="elearning-owner-section"><h2>{copy("title")}</h2>
    <OwnerStatus value={decision.status}>{t(`elearning.programmes.${decision.status}`)}</OwnerStatus>
    {kind!=="none" && <p>{copy("domain_help")}</p>}
    {error && <LearningErrorNotice as="p">{copy("changed")}</LearningErrorNotice>}
    {options.length>0 && <form className="elearning-course-form" onSubmit={save}>
      <label>{t("elearning.owner.status")}<select value={status} onChange={event=>setStatus(event.target.value)}>{options.map(value=><option key={value} value={value}>{t(`elearning.programmes.${value}`)}</option>)}</select></label>
      <label>{t("elearning.programmes.note")}<textarea required maxLength={4000} dir="auto" value={note} onChange={event=>setNote(event.target.value)} /></label>
      <button type="submit" disabled={busy} className="ecommerce-primary-button">{copy("record")}</button>
    </form>}
    <OwnerTable caption={t("elearning.programmes.history")} columns={[t("elearning.owner.status"),t("elearning.programmes.note"),copy("reviewer"),t("elearning.ui.submitted")]}>
      {(response.decision_history || []).map(entry=><tr key={entry.revision}><td>{t(`elearning.programmes.${entry.new_status}`)}</td><td dir="auto">{entry.note}</td><td>{entry.reviewer_name || `${copy("reviewer")} ${entry.actor_id}`}</td><td>{new Date(entry.created_at).toLocaleString(i18n.language)}</td></tr>)}
    </OwnerTable>
  </section>;
}
