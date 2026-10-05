import { useContext } from "react";
import { ELearningTerminologyContext } from "../context/ELearningTerminologyContext";

export function useELearningTerminology() { return useContext(ELearningTerminologyContext); }
