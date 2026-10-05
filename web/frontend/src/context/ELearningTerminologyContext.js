import { createContext } from "react";
import { getELearningTerminology } from "../config/elearningTerminology";

export const ELearningTerminologyContext = createContext({ labels: getELearningTerminology(), loading: false, error: null, updateSettings: () => {}, retry: () => {} });
