import {
  getFormSections,
  getFormFields,
} from "./PageBuilder.factories";
import {
  getModernFieldPlaceholder,
  scaleRange,
} from "./PageBuilder.fields";
import {
  getQuizSettings,
  formatQuizTime,
} from "./PageBuilder.quiz";
import {
  getDefaultFormLanguage,
  getDirectionForLanguage,
  getLocalizedOptions,
  getLocalizedValue,
  getRuntimeLanguage,
  normalizeLanguageMode,
} from "./PageBuilder.localization";

const getContentDirection = (value, fallback = "ltr") =>
  /[\u0590-\u05ff\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]/.test(String(value || ""))
    ? "rtl"
    : fallback;

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

export const createRuntimeFormRenderers = ({
  project,
  lang = "en",
  runtimeAnswers,
  runtimeErrors,
  runtimeFormPages,
  setRuntimeFormPages,
  runtimeFormLanguages,
  setRuntimeFormLanguages,
  quizSessions,
  getFieldType,
  setAnswer,
  submitRuntimeForm,
  startQuizSession,
  moveQuizQuestion,
}) => {
  const setFormPage = (formId, pageIndex, pageCount = 1) => {
    setRuntimeFormPages?.((prev) => ({
      ...prev,
      [formId]: Math.max(0, Math.min(pageIndex, Math.max(pageCount - 1, 0))),
    }));
  };

  const changeFormPage = (event, formId, pageIndex, pageCount) => {
    const formElement = event.currentTarget.closest(".runtime-form");
    const previewScroller = formElement?.closest(".forms-live-preview-page, .simple-preview-panel");
    setFormPage(formId, pageIndex, pageCount);
    requestAnimationFrame(() => {
      if (previewScroller) {
        previewScroller.scrollTo({ top: 0, behavior: "smooth" });
      } else {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    });
  };

  const renderFieldInput = (form, field, disabled = false, activeFormLang = null) => {
    const formLang = activeFormLang || getRuntimeLanguage(form, lang);
    const rawValue = runtimeAnswers[form.id]?.[field.id] ?? field.defaultValue ?? "";
    const value = getAnswerValue(rawValue);
    const error = runtimeErrors[field.id];
    const meta = getFieldType(field.type);
    const placeholder = field.showDetailsEditor === true
      ? getLocalizedValue(field, "placeholder", formLang) || getModernFieldPlaceholder(field)
      : "";
    const label = getLocalizedValue(field, "label", formLang) || field.label;
    const helpText = field.showDetailsEditor === true
      ? getLocalizedValue(field, "helpText", formLang) || field.helpText
      : "";
    const options = getLocalizedOptions(field, formLang).filter((option) => String(option || "").trim());
    const fieldDirection = getContentDirection(
      `${label || ""} ${helpText || ""} ${options.join(" ")}`,
      getDirectionForLanguage(formLang)
    );
    const baseId = `${form.id}_${field.id}`;

    const common = {
      disabled,
      value,
      onChange: (event) => setAnswer(form.id, field.id, event.target.value),
    };

    let inputNode = null;

    if (["text", "email", "tel", "number", "date", "time", "url"].includes(meta.input)) {
      inputNode = <input type={meta.input} dir={fieldDirection} placeholder={placeholder} {...common} />;
    } else if (meta.input === "textarea") {
      inputNode = <textarea dir={fieldDirection} placeholder={placeholder} {...common} />;
    } else if (meta.input === "select") {
      inputNode = (
        <select dir={fieldDirection} {...common}>
          <option value="">{placeholder}</option>
          {options.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      );
    } else if (meta.input === "radio") {
      inputNode = (
        <div className="runtime-choice-list">
          {options.map((option, optionIndex) => {
            const optionId = `${baseId}_${optionIndex}`;

            return (
            <label
              className="runtime-choice"
              key={optionId}
              htmlFor={optionId}
              dir={getContentDirection(option, fieldDirection)}
            >
              <input
                id={optionId}
                type="radio"
                name={baseId}
                value={option}
                checked={isOptionAnswerChecked(rawValue, option, optionIndex)}
                disabled={disabled}
                onChange={(event) =>
                  setAnswer(form.id, field.id, {
                    value: event.target.value,
                    optionIndex,
                  })
                }
              />
              <span dir={getContentDirection(option, fieldDirection)}>{option}</span>
            </label>
            );
          })}
        </div>
      );
    } else if (meta.input === "checkboxes") {
      const values = Array.isArray(runtimeAnswers[form.id]?.[field.id])
        ? runtimeAnswers[form.id][field.id]
        : [];

      inputNode = (
        <div className="runtime-choice-list">
          {options.map((option, optionIndex) => {
            const optionId = `${baseId}_${optionIndex}`;

            return (
            <label
              className="runtime-choice"
              key={optionId}
              htmlFor={optionId}
              dir={getContentDirection(option, fieldDirection)}
            >
              <input
                id={optionId}
                type="checkbox"
                value={option}
                checked={isCheckboxOptionChecked(values, option, optionIndex)}
                disabled={disabled}
                onChange={(event) => {
                  const next = event.target.checked
                    ? [...values, { value: option, optionIndex }]
                    : values.filter((item) => {
                        if (item && typeof item === "object" && !Array.isArray(item)) {
                          return item.optionIndex !== optionIndex;
                        }

                        return item !== option;
                      });
                  setAnswer(form.id, field.id, next);
                }}
              />
              <span dir={getContentDirection(option, fieldDirection)}>{option}</span>
            </label>
            );
          })}
        </div>
      );
    } else if (meta.input === "linearScale") {
      inputNode = (
        <div className="scale-choice">
          <span>{field.scaleMinLabel || field.scaleMin || 1}</span>
          {scaleRange(field).map((option) => (
            <button
              type="button"
              key={option}
              disabled={disabled}
              className={value === option ? "active" : ""}
              onClick={() => setAnswer(form.id, field.id, option)}
            >
              {option}
            </button>
          ))}
          <span>{field.scaleMaxLabel || field.scaleMax || 5}</span>
        </div>
      );
    } else if (meta.input === "rating") {
      const maxRating = Math.max(2, Math.min(10, Number(field.maxRating || 5)));
      inputNode = (
        <div className="rating-choice">
          {Array.from({ length: maxRating }, (_, index) => String(index + 1)).map((option) => (
            <button
              type="button"
              key={option}
              disabled={disabled}
              className={Number(value) >= Number(option) ? "active" : ""}
              onClick={() => setAnswer(form.id, field.id, option)}
            >
              {option}
            </button>
          ))}
        </div>
      );
    } else if (meta.input === "yesNo") {
      inputNode = (
        <div className="choice-pills">
          {(formLang === "ar" ? ["نعم", "لا"] : ["Yes", "No"]).map((option) => (
            <button
              type="button"
              key={option}
              disabled={disabled}
              className={value === option ? "active" : ""}
              onClick={() => setAnswer(form.id, field.id, option)}
            >
              {option}
            </button>
          ))}
        </div>
      );
    } else if (meta.input === "file") {
      inputNode = (
        <input
          type="file"
          disabled={disabled}
          onChange={(event) => {
            const file = event.target.files?.[0];
            setAnswer(form.id, field.id, file ? { name: file.name, size: file.size, type: file.type } : "");
          }}
        />
      );
    }

    return (
      <div className={`runtime-question ${error ? "has-error" : ""}`} key={field.id}>
        <label dir={fieldDirection}>
          <span className="runtime-question-title" dir={fieldDirection}>
            {label}
            {field.required && <span className="form-required-marker" aria-hidden="true"> *</span>}
          </span>
          {helpText && <small dir={getContentDirection(helpText, fieldDirection)}>{helpText}</small>}
          {inputNode}
          {error && <strong>{error}</strong>}
        </label>
      </div>
    );
  };

  const renderConnectedForm = (formId, { allowInteraction = false } = {}) => {
    const form = project.forms.find((item) => String(item.id) === String(formId || ""));
    if (!form) return <div className="empty-connected">No form selected.</div>;
    const formLang = runtimeFormLanguages?.[form.id] || getDefaultFormLanguage(form, lang);
    const formDir = getDirectionForLanguage(formLang);
    const languageMode = normalizeLanguageMode(form.languageMode || lang);
    const isQuiz = form.mode === "quiz";
    const quizSettings = getQuizSettings(form);
    const quizFields = getFormFields(form);
    const quizSession = quizSessions[form.id];
    const quizLocked = Boolean(quizSession?.locked);
    const quizStarted = !isQuiz || quizSession?.active;
    const currentQuestionIndex = Math.min(quizSession?.currentIndex || 0, Math.max(quizFields.length - 1, 0));
    const currentField = quizFields[currentQuestionIndex];
    const formSections = getFormSections(form);
    const isPagedForm = formSections.length > 1;
    const currentPageIndex = Math.max(
      0,
      Math.min(Number(runtimeFormPages?.[form.id] || 0), Math.max(formSections.length - 1, 0))
    );
    const currentPage = formSections[currentPageIndex];
    const renderRuntimeFormPage = (section) => (
      <div className="runtime-form-section" key={section.id}>
        <div className="runtime-form-section-header">
          <h1 className="form-page-title" dir={section.titleStyle?.direction} style={{ ...(section.titleStyle || {}), textStyle: undefined }}>{getLocalizedValue(section, "title", formLang) || section.title}</h1>
          {(getLocalizedValue(section, "description", formLang) || section.description) && (
            <h2 className="form-page-description" dir={section.descriptionStyle?.direction} style={{ ...(section.descriptionStyle || {}), textStyle: undefined }}>{getLocalizedValue(section, "description", formLang) || section.description}</h2>
          )}
        </div>

        {(section.fields || []).map((field) => renderFieldInput(form, field, !allowInteraction, formLang))}
      </div>
    );

    return (
      <div
        className={`runtime-form ${isQuiz ? "runtime-quiz-form" : ""} ${quizSettings.lockScreen ? "runtime-quiz-lockable" : ""}`}
        dir={formDir}
      >
        <div className="runtime-form-header">
          {languageMode === "bilingual" && (
            <div className="runtime-language-switch" role="group" aria-label="Form language">
              <button
                type="button"
                className={formLang === "en" ? "active" : ""}
                onClick={() => setRuntimeFormLanguages?.((prev) => ({ ...prev, [form.id]: "en" }))}
              >
                English
              </button>
              <button
                type="button"
                className={formLang === "ar" ? "active" : ""}
                onClick={() => setRuntimeFormLanguages?.((prev) => ({ ...prev, [form.id]: "ar" }))}
              >
                العربية
              </button>
            </div>
          )}
          {isQuiz && (
            <div className="quiz-runtime-meta">
              <span>{quizFields.length} questions</span>
              {quizSettings.totalTimeLimitSec > 0 && (
                <span>Total: {formatQuizTime(quizStarted ? quizSession?.totalRemaining : quizSettings.totalTimeLimitSec)}</span>
              )}
              {quizSettings.questionTimeLimitSec > 0 && (
                <span>Per question: {formatQuizTime(quizSettings.questionTimeLimitSec)}</span>
              )}
              {quizSettings.lockScreen && <span>Focus mode</span>}
            </div>
          )}
        </div>

        {isQuiz && quizLocked ? (
          <div className="quiz-start-panel">
            <strong>Quiz locked</strong>
            <p>{quizSession?.lockedReason || "Focus mode was interrupted. This quiz cannot be continued or retaken."}</p>
          </div>
        ) : isQuiz && !quizStarted ? (
          <div className="quiz-start-panel">
            <strong>Ready to start?</strong>
            <p>
              {quizSettings.lockScreen
                ? "This quiz opens in focus mode. Timers begin when you start."
                : "Timers begin when you start the quiz."}
            </p>
            <button
              type="button"
              className="runtime-submit"
              disabled={!allowInteraction || quizFields.length === 0}
              onClick={() => startQuizSession(form)}
            >
              Start quiz
            </button>
          </div>
        ) : isQuiz ? (
          <div className="runtime-form-section quiz-question-stage">
            <div className="runtime-form-section-header">
              <h4>Question {currentQuestionIndex + 1} of {quizFields.length}</h4>
              {quizSession?.questionRemaining > 0 && (
                <p>Question time: {formatQuizTime(quizSession.questionRemaining)}</p>
              )}
            </div>

            {currentField && renderFieldInput(form, currentField, !allowInteraction, formLang)}

            <div className="quiz-navigation">
              <button
                type="button"
                disabled={!allowInteraction || currentQuestionIndex === 0}
                onClick={() => moveQuizQuestion(form, "previous")}
              >
                Previous
              </button>
              {currentQuestionIndex < quizFields.length - 1 ? (
                <button
                  type="button"
                  disabled={!allowInteraction}
                  onClick={() => moveQuizQuestion(form, "next")}
                >
                  Next
                </button>
              ) : (
                <button
                  type="button"
                  className="runtime-submit"
                  disabled={!allowInteraction}
                  onClick={() => submitRuntimeForm(form)}
                >
                  Submit quiz
                </button>
              )}
            </div>
          </div>
        ) : (
          <>
            {isPagedForm && (
              <div className="form-page-counter-title">Page {currentPageIndex + 1} of {formSections.length}</div>
            )}
            {isPagedForm
              ? currentPage
                ? renderRuntimeFormPage(currentPage)
                : null
              : formSections.map((section) => renderRuntimeFormPage(section))}

            <div className="runtime-form-pagination">
              {isPagedForm ? (
                <button
                  type="button"
                  disabled={currentPageIndex === 0}
                  onClick={(event) => changeFormPage(event, form.id, currentPageIndex - 1, formSections.length)}
                >
                  Previous
                </button>
              ) : (
                <span />
              )}

              <span className="runtime-form-page-count">
                {isPagedForm ? `Page ${currentPageIndex + 1} of ${formSections.length}` : ""}
              </span>

              {isPagedForm && currentPageIndex < formSections.length - 1 ? (
                <button
                  type="button"
                  onClick={(event) => changeFormPage(event, form.id, currentPageIndex + 1, formSections.length)}
                >
                  Next
                </button>
              ) : (
                <button
                  type="button"
                  className="runtime-submit"
                  disabled={!allowInteraction}
                  onClick={() => submitRuntimeForm(form)}
                >
                  Submit
                </button>
              )}
            </div>
          </>
        )}

        {!allowInteraction && <p className="builder-note">Preview is read-only in the builder. Published forms collect responses from visitors.</p>}
      </div>
    );
  };

  return {
    renderFieldInput,
    renderConnectedForm,
  };
};
