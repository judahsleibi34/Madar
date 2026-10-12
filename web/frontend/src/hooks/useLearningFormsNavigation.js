import { useEffect, useState } from "react";
import { learningFormsApi } from "../components/ELearning/learningFormsApi";
export default function useLearningFormsNavigation(user, allowed) {
  const identity = `${user?.tenant_id}:${user?.id}`;
  const [state,setState] = useState(null);
  useEffect(() => {
    if (!allowed) return;
    let active = true;
    const refresh = () => learningFormsApi().then(value => {if (active) setState({identity,value});}).catch(() => {if (active) setState(null);});
    refresh();window.addEventListener("learning-forms-changed",refresh);return () => {active = false;window.removeEventListener("learning-forms-changed",refresh);};
  }, [identity,allowed]);
  return allowed && state?.identity === identity ? state.value : null;
}
