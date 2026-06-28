import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { STORAGE_KEY } from "../core/PageBuilder.constants";
import { getFormSections } from "../core/PageBuilder.factories";
import {
  getDefaultFormLanguage,
  getDirectionForLanguage,
  getLocalizedOptions,
  getLocalizedValue,
  normalizeLanguageMode,
} from "../core/PageBuilder.localization";
import { cleanBuilderProject } from "../core/PageBuilder.project";
import { getQuizSettings } from "../core/PageBuilder.quiz";
import { getPageBuilderThemeVars } from "../core/PageBuilder.theme";
import "../../../styles/admin/PageBuilder/index.css";

const loadDraftProject = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? cleanBuilderProject(JSON.parse(raw)) : null;
  } catch {
    return null;
  }
};

const getFieldOptions = (field = {}, lang = "en") =>
  getLocalizedOptions(field, lang).filter((option) =>
    String(option || "").trim()
  );

const isEmptyAnswer = (value) =>
  Array.isArray(value) ? value.length === 0 : String(value ?? "").trim() === "";

const getAnswerValue = (answer) =>
  answer && typeof answer === "object" && !Array.isArray(answer) && "value" in answer
    ? answer.value
    : answer;

const isOptionAnswerChecked = (answer, option, optionIndex) => {
  if (answer && typeof answer === "object" && !Array.isArray(answer)) {
    return answer.optionIndex === optionIndex;
  }
  return answer === option;
};

const isCheckboxOptionChecked = (answers, option, optionIndex) =>
  answers.some((answer) => {
    if (answer && typeof answer === "object" && !Array.isArray(answer)) {
      return answer.optionIndex === optionIndex;
    }
    return answer === option;
  });

export default function BuilderFormPreviewPage() {
  const { formId = "" } = useParams();
  const navigate = useNavigate();
  const [project] = useState(loadDraftProject);
  const form = useMemo(
    () => project?.forms?.find((item) => item.id === formId) || project?.forms?.[0] || null,
    [formId, project?.forms]
  );
  const sections = useMemo(() => getFormSections(form), [form]);
  const languageMode = normalizeLanguageMode(form?.languageMode || form?.localeMode || "en");
  const [formLang, setFormLang] = useState(() => getDefaultFormLanguage(form, "en"));
  const formDirection = getDirectionForLanguage(formLang);
  const isPagedForm = (form?.pageMode || "paged") === "paged" && sections.length > 1;
  const [pageIndex, setPageIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [quizStarted, setQuizStarted] = useState(false);
  const [quizDeactivated, setQuizDeactivated] = useState(false);
  const quizCompleteRef = useRef(false);
  const currentSection = sections[Math.min(pageIndex, Math.max(sections.length - 1, 0))];
  const isQuiz = form?.mode === "quiz";
  const quizSettings = useMemo(() => getQuizSettings(form), [form]);

  useEffect(() => {
    quizCompleteRef.current = false;
    setQuizStarted(!isQuiz);
    setQuizDeactivated(false);
    setSubmitted(false);
    setPageIndex(0);
    setFormError("");
    setFormLang(getDefaultFormLanguage(form, "en"));
  }, [form?.id, isQuiz]);

  useEffect(() => {
    if (!isQuiz || !quizSettings.lockScreen || !quizStarted || submitted) return undefined;

    const deactivateFocusedAttempt = () => {
      if (!quizCompleteRef.current) {
        setQuizDeactivated(true);
        setQuizStarted(false);
        setFormError("Focus mode was interrupted. This quiz attempt is locked and cannot be retaken.");
      }
    };

    const handleFullscreenChange = () => {
      if (!document.fullscreenElement) deactivateFocusedAttempt();
    };

    const handleVisibilityChange = () => {
      if (document.hidden) deactivateFocusedAttempt();
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("blur", deactivateFocusedAttempt);
    window.addEventListener("pagehide", deactivateFocusedAttempt);

    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("blur", deactivateFocusedAttempt);
      window.removeEventListener("pagehide", deactivateFocusedAttempt);
    };
  }, [isQuiz, quizSettings.lockScreen, quizStarted, submitted]);

  const setAnswer = (fieldId, value) => {
    setAnswers((current) => ({ ...current, [fieldId]: value }));
    setErrors((current) => ({ ...current, [fieldId]: "" }));
    setFormError("");
  };

  const validateFields = (fields = []) => {
    const nextErrors = {};
    fields.forEach((field) => {
      if (field.required && isEmptyAnswer(answers[field.id])) {
        nextErrors[field.id] = "This question is required.";
      }
    });
    setErrors((current) => ({ ...current, ...nextErrors }));
    return Object.keys(nextErrors).length === 0;
  };

  const goNext = () => {
    setFormError("");
    setPageIndex((current) => Math.min(current + 1, sections.length - 1));
  };

  const goPrevious = () => {
    setFormError("");
    setPageIndex((current) => Math.max(current - 1, 0));
  };

  const submitForm = (event) => {
    event.preventDefault();
    if (quizDeactivated) return;
    const allFields = sections.flatMap((section) => section.fields || []);
    if (!validateFields(allFields)) {
      const firstInvalidSectionIndex = sections.findIndex((section) =>
        (section.fields || []).some((field) => field.required && isEmptyAnswer(answers[field.id]))
      );
      if (firstInvalidSectionIndex >= 0) {
        setPageIndex(firstInvalidSectionIndex);
      }
      setFormError("Please answer the required questions before submitting.");
      return;
    }
    setFormError("");
    quizCompleteRef.current = true;
    setSubmitted(true);
    if (document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => undefined);
    }
  };

  const startQuiz = async () => {
    if (quizDeactivated) {
      setFormError("Focus mode was interrupted. This quiz attempt cannot be retaken.");
      return;
    }

    setFormError("");
    quizCompleteRef.current = false;

    if (quizSettings.lockScreen) {
      if (!document.documentElement.requestFullscreen) {
        setQuizDeactivated(true);
        setFormError("Fullscreen is required for focus mode, but this browser does not support it. This quiz attempt cannot be retaken.");
        return;
      }

      try {
        await document.documentElement.requestFullscreen();
      } catch {
        setFormError("Fullscreen is required before this quiz can start.");
        return;
      }
    }

    setQuizStarted(true);
  };

  const renderField = (field) => {
    const rawValue = answers[field.id] ?? "";
    const value = getAnswerValue(rawValue);
    const options = getFieldOptions(field, formLang);
    const label = getLocalizedValue(field, "label", formLang) || field.label;
    const helpText = getLocalizedValue(field, "helpText", formLang) || field.helpText;
    const placeholder = getLocalizedValue(field, "placeholder", formLang) || field.placeholder || "";

    let input = null;
    if (field.type === "paragraph") {
      input = <textarea value={value} placeholder={placeholder} onChange={(event) => setAnswer(field.id, event.target.value)} />;
    } else if (field.type === "dropdown" || field.type === "status") {
      input = (
        <select value={value} onChange={(event) => setAnswer(field.id, event.target.value)}>
          <option value="">Select an option</option>
          {options.map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
      );
    } else if (field.type === "radio" || field.type === "yesNo") {
      const choices = field.type === "yesNo" ? (formLang === "ar" ? ["نعم", "لا"] : ["Yes", "No"]) : options;
      input = (
        <div className="builder-form-preview-options">
          {choices.map((option, optionIndex) => (
            <label key={option}>
              <input
                type="radio"
                name={field.id}
                checked={isOptionAnswerChecked(rawValue, option, optionIndex)}
                onChange={() => setAnswer(field.id, { value: option, optionIndex })}
              />
              <span>{option}</span>
            </label>
          ))}
        </div>
      );
    } else if (field.type === "checkboxes") {
      const selected = Array.isArray(rawValue) ? rawValue : [];
      input = (
        <div className="builder-form-preview-options">
          {options.map((option, optionIndex) => (
            <label key={option}>
              <input
                type="checkbox"
                checked={isCheckboxOptionChecked(selected, option, optionIndex)}
                onChange={(event) =>
                  setAnswer(
                    field.id,
                    event.target.checked
                      ? [...selected, { value: option, optionIndex }]
                      : selected.filter((item) => {
                          if (item && typeof item === "object" && !Array.isArray(item)) {
                            return item.optionIndex !== optionIndex;
                          }
                          return item !== option;
                        })
                  )
                }
              />
              <span>{option}</span>
            </label>
          ))}
        </div>
      );
    } else if (field.type === "file") {
      input = <input type="file" onChange={(event) => setAnswer(field.id, event.target.files?.[0]?.name || "")} />;
    } else {
      const inputType = field.type === "email" ? "email" : field.type === "number" || field.type === "money" ? "number" : field.type === "date" ? "date" : "text";
      input = <input type={inputType} value={value} placeholder={placeholder} onChange={(event) => setAnswer(field.id, event.target.value)} />;
    }

    return (
      <div className="builder-form-preview-question" key={field.id}>
        <label>
          <span>{label}{field.required ? " *" : ""}</span>
          {helpText && <small>{helpText}</small>}
          {input}
        </label>
        {errors[field.id] && <strong>{errors[field.id]}</strong>}
      </div>
    );
  };

  if (!form) {
    return (
      <main className="builder-form-preview-page" style={getPageBuilderThemeVars(project?.theme)}>
        <section className="builder-form-preview-shell">
          <h1>No form found</h1>
          <button type="button" onClick={() => navigate("/page-builder")}>Back to builder</button>
        </section>
      </main>
    );
  }

  return (
    <main className="builder-form-preview-page" dir={formDirection} style={getPageBuilderThemeVars(project?.theme)}>
      <header className="builder-form-preview-topbar">
        <button type="button" onClick={() => navigate("/page-builder")}>
          <ArrowLeft size={16} aria-hidden="true" />
          Back to builder
        </button>
        <strong>Form preview</strong>
      </header>

      <form className="builder-form-preview-shell" onSubmit={submitForm}>
        <div className="builder-form-preview-header">
          {languageMode === "bilingual" && (
            <div className="runtime-language-switch" role="group" aria-label="Form language">
              <button type="button" className={formLang === "en" ? "active" : ""} onClick={() => setFormLang("en")}>
                English
              </button>
              <button type="button" className={formLang === "ar" ? "active" : ""} onClick={() => setFormLang("ar")}>
                العربية
              </button>
            </div>
          )}
          <h1>{getLocalizedValue(form, "title", formLang) || form.title || "Untitled form"}</h1>
          {(getLocalizedValue(form, "description", formLang) || form.description) && (
            <p>{getLocalizedValue(form, "description", formLang) || form.description}</p>
          )}
        </div>

        {submitted ? (
          <section className="builder-form-preview-success">
            <h2>Submitted</h2>
            <p>{getLocalizedValue(form, "successMessage", formLang) || form.successMessage || "Thank you. Your response has been submitted."}</p>
          </section>
        ) : quizDeactivated ? (
          <section className="builder-form-preview-quiz-state">
            <h2>Quiz locked</h2>
            <p>Focus mode was interrupted before submission, so this quiz cannot be continued or retaken.</p>
          </section>
        ) : isQuiz && !quizStarted ? (
          <section className="builder-form-preview-quiz-state">
            <h2>Ready to start?</h2>
            <p>
              {quizSettings.lockScreen
                ? "This quiz opens in fullscreen focus mode. Leaving fullscreen will deactivate the attempt."
                : "Start the quiz when you are ready to answer the questions."}
            </p>
            <button type="button" onClick={startQuiz}>Start quiz</button>
          </section>
        ) : (
          <>
            {(isPagedForm ? [currentSection] : sections).filter(Boolean).map((section, index) => (
              <section className="builder-form-preview-section" key={section.id}>
                {(getLocalizedValue(section, "title", formLang) || section.title) && section !== sections[0] && (
                  <h2>{getLocalizedValue(section, "title", formLang) || section.title}</h2>
                )}
                {(getLocalizedValue(section, "description", formLang) || section.description) && (
                  <p>{getLocalizedValue(section, "description", formLang) || section.description}</p>
                )}
                {(section.fields || []).map(renderField)}
              </section>
            ))}

            {formError && <p className="builder-form-preview-error">{formError}</p>}

            <footer className={`builder-form-preview-actions ${isPagedForm ? "is-paged" : "is-single"}`}>
              {isPagedForm && (
                <button type="button" disabled={pageIndex === 0} onClick={goPrevious}>
                  Previous
                </button>
              )}
              {isPagedForm && <span>Page {pageIndex + 1} of {sections.length}</span>}
              {isPagedForm && pageIndex < sections.length - 1 ? (
                <button type="button" onClick={goNext}>Next</button>
              ) : (
                <button type="submit">Submit</button>
              )}
            </footer>
          </>
        )}
      </form>
    </main>
  );
}
