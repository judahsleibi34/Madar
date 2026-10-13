import { createContext, useContext } from "react";

// Per-academy opt-in improvements (see academyExperience in the academy website).
// Absent flags keep each academy's existing behaviour.
export const LearningExperienceContext = createContext({});
export const useLearningExperience = () => useContext(LearningExperienceContext);
