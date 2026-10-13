import LearningErrorNotice from "../../ELearning/LearningErrorNotice";
import { Link, useLocation } from "react-router-dom";
import { getBrandedMadarSubdomain } from "../../../utils/hostedAddress";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { learningFormsApi } from "../../ELearning/learningFormsApi";
import LearningFormRenderer from "../../ELearning/LearningFormRenderer";
import { apiFetch, getApiUrl } from "../../../utils/apiClient";
export default function AcademyFormBlock({ formId, identifier, editing }) {
  const location = useLocation();
  const {t} = useTranslation("dashboard");
  const identity = `${formId}:${identifier}:${editing}`;
  const base = getBrandedMadarSubdomain(window.location.hostname) ? "/academy" : `/academy/${encodeURIComponent(identifier)}`;
  const loginPath = `${base}/login?returnTo=${encodeURIComponent(location.pathname + location.search + location.hash)}`;
  const [state,setState] = useState({});
  useEffect(() => {let active = true;if (!formId) return;const request = editing ? learningFormsApi(`/${formId}`) : apiFetch(getApiUrl(`/public/academies/${encodeURIComponent(identifier)}/forms/${formId}`),{cache:"no-store"}).then(async response => {if (!response.ok) throw Object.assign(new Error(), { status: response.status });return response.json();});request.then(form => {if (active) setState({identity,form});}).catch(error => {if (active) setState({identity,error:true,status:error.status});});return () => {active = false;};}, [formId,identifier,editing,identity]);
  if (!formId) return editing ? <p>{t("elearning.forms.select")}</p> : null;
  if (state.identity !== identity) return <p role="status">{t("elearning.forms.loading")}</p>;
  if (state.error && state.status === 401) return <p><Link to={loginPath}>{t("elearning.learner.logIn")}</Link></p>;
  if (state.error && state.status === 403) return <p role="status">{t("elearning.forms.locked_unavailable")}</p>;
  if (state.error) return <LearningErrorNotice as="p">{t("elearning.forms.unavailable")}</LearningErrorNotice>;
  return <LearningFormRenderer key={`${formId}:${state.form.version}:${editing}`} form={state.form} identifier={identifier} preview={editing} loginPath={loginPath} />;
}
