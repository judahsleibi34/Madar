import { createContext, useContext } from "react";

// "L03-T02": the media-list prefix for the lesson being edited (Level, Topic).
export const LessonMediaNamingContext = createContext("");
export const useLessonMediaPrefix = () => useContext(LessonMediaNamingContext);
export const mediaPrefix = (level, topic) => level && topic ? `L${String(level).padStart(2, "0")}-T${String(topic).padStart(2, "0")}` : "";
