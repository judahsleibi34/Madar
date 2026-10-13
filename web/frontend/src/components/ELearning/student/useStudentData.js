import { useContext, useEffect, useState } from "react";
import { fetchLearningCourse, fetchMyLearning, fetchReferralAccount } from "../../../services/elearningPlayer";
import { request } from "../academyProgrammeApi";
import { StudentDataContext } from "./StudentDataContext";

/**
 * Everything the EduHope student dashboard shows, from existing learner APIs:
 * enrolled course and its Levels, referral account, wallet and applications.
 * Each part fails independently so one unavailable programme never blanks the page.
 */
export default function useStudentData({ withCourse = true } = {}) {
  const sample = useContext(StudentDataContext);
  const [state, setState] = useState({ loading: true });
  const [reload, setReload] = useState(0);
  useEffect(() => {
    if (sample) return undefined;
    let active = true;
    const optional = promise => promise.then(value => value, () => null);
    (async () => {
      const learning = await fetchMyLearning().catch(error => ({ error }));
      const enrolled = learning?.courses?.[0] || null;
      const [course, referrals, programmes] = await Promise.all([
        withCourse && enrolled ? optional(fetchLearningCourse(enrolled.course.id)) : null,
        optional(fetchReferralAccount()),
        optional(request("/account")),
      ]);
      if (active) setState({ loading: false, error: learning?.error || null, learning, enrolled, course, referrals, programmes });
    })();
    return () => { active = false; };
  }, [withCourse, reload, sample]);
  if (sample) return { loading: false, error: null, ...sample, retry: () => {} };
  return { ...state, retry: () => { setState({ loading: true }); setReload(value => value + 1); } };
}
