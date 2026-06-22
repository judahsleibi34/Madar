const splitLines = (value) =>
  String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

export default function FormsTab({
  project,
  activeForm,
  fieldTypes,
  selected,

  selectForm,
  selectPage,
  setActiveTab,
  setDesignPanel,
  setSelected,

  addForm,
  addFormSection,
  addFieldToForm,
  updateActiveForm,
  updateActiveFormQuiz,
  updateFormField,
  updateFormSection,
  renderQuizAnswerKeyEditor,
  moveFormField,
  duplicateFormField,
  deleteFormField,
  deleteFormSection,

  getFormFields,
  getFormSections,
  getQuizSettings,
  getFormPlacements,
  addConnectedFormSectionToPage,
  renderConnectedForm,

  quizOptionsOpen,
  setQuizOptionsOpen,
}) {
  const getFieldType = (type) =>
    fieldTypes.find((item) => item.id === type) || fieldTypes[0];

  const commonFieldTypes = [
    "shortText",
    "paragraph",
    "email",
    "phone",
    "url",
    "number",
    "date",
    "time",
    "dropdown",
    "radio",
    "checkboxes",
    "yesNo",
    "linearScale",
    "rating",
    "file",
  ];

  const placements = activeForm ? getFormPlacements(activeForm.id) : [];

  return (
    <div className="workspace-page forms-google-workspace">
      <div className="workspace-header">
        <div>
          <h2>Forms</h2>
          <p>Build forms like a document, preview them live, and place them on any page.</p>
        </div>
        <button type="button" onClick={addForm}>+ Form</button>
      </div>

      <div className="forms-top-stack">
        <section className="object-list google-form-list forms-form-strip" aria-label="Forms">
          {project.forms.map((form) => (
            <button
              key={form.id}
              type="button"
              className={activeForm?.id === form.id ? "active" : ""}
              onClick={() => selectForm(form.id)}
            >
              <strong>{form.title}</strong>
              <span>{getFormFields(form).length} fields / {form.responses.length} responses</span>
            </button>
          ))}
        </section>

        <section className="forms-settings-top google-form-actions">
          <section className="quiz-settings-panel quiz-settings-summary">
            <div className="quiz-settings-header">
              <div>
                <h3>Quiz Settings</h3>
                <p>
                  {activeForm?.mode === "quiz"
                    ? "Quiz mode is enabled for this form."
                    : "Keep this as a form or turn it into a timed quiz."}
                </p>
              </div>
              <label className="checkbox-control">
                <input
                  type="checkbox"
                  checked={activeForm?.mode === "quiz"}
                  onChange={(event) =>
                    updateActiveForm((form) => ({
                      ...form,
                      mode: event.target.checked ? "quiz" : "form",
                      quiz: getQuizSettings(form),
                    }))
                  }
                />
                Quiz
              </label>
            </div>
            <button
              type="button"
              className="quiz-options-trigger"
              onClick={() => setQuizOptionsOpen(true)}
            >
              Quiz options
            </button>
          </section>

          <section className="form-placement-panel">
            <h3>Place Form</h3>
            <label>
              Page
              <select
                value={project.activePageId || ""}
                onChange={(event) => selectPage(event.target.value)}
              >
                {project.pages.map((page) => (
                  <option key={page.id} value={page.id}>{page.name}</option>
                ))}
              </select>
            </label>
            <div className="form-panel-actions">
              <button
                type="button"
                className="primary-action"
                onClick={() => addConnectedFormSectionToPage(activeForm?.id)}
              >
                Add to page
              </button>
            </div>
            {placements.length > 0 && (
              <div className="connected-placement-list">
                <span>Placed on:</span>
                {placements.map((placement) => (
                  <button
                    type="button"
                    key={`${placement.pageId}_${placement.sectionName}`}
                    onClick={() => {
                      selectPage(placement.pageId);
                      setActiveTab("design");
                      setDesignPanel("Layers");
                    }}
                  >
                    {placement.pageName}
                  </button>
                ))}
              </div>
            )}
          </section>

          <section className="form-save-panel">
            <h3>Save Data</h3>
            <label>
              Save submissions to
              <select
                value={activeForm?.connectedCollectionId || ""}
                onChange={(event) =>
                  updateActiveForm((form) => ({
                    ...form,
                    connectedCollectionId: event.target.value,
                  }))
                }
              >
                <option value="">Form submissions only</option>
                {project.collections.map((collection) => (
                  <option key={collection.id} value={collection.id}>{collection.name}</option>
                ))}
              </select>
            </label>
            <label>
              Success message
              <textarea
                value={activeForm?.successMessage || ""}
                onChange={(event) =>
                  updateActiveForm((form) => ({
                    ...form,
                    successMessage: event.target.value,
                  }))
                }
              />
            </label>
          </section>

          <details className="form-preview-panel">
            <summary>Preview</summary>
            {activeForm && renderConnectedForm(activeForm.id, { allowInteraction: true })}
          </details>
        </section>
      </div>

      <div className="google-form-layout">
        <main className="google-form-document">
          {activeForm && (
            <>
              <div className="google-form-title-card">
                <input
                  className="google-form-title-input"
                  value={activeForm.title}
                  onChange={(event) =>
                    updateActiveForm((form) => ({
                      ...form,
                      title: event.target.value,
                    }))
                  }
                />
                <textarea
                  className="google-form-description-input"
                  value={activeForm.description}
                  placeholder="Form description"
                  onChange={(event) =>
                    updateActiveForm((form) => ({
                      ...form,
                      description: event.target.value,
                    }))
                  }
                />
              </div>

              <div className="google-add-strip">
                {commonFieldTypes.map((typeId) => {
                  const type = getFieldType(typeId);
                  return (
                    <button key={type.id} type="button" onClick={() => addFieldToForm(type.id)}>
                      + {type.label}
                    </button>
                  );
                })}
                <button type="button" className="add-section-control" onClick={addFormSection}>
                  + Section
                </button>
              </div>

              <div className="form-sections-stack">
                {getFormSections(activeForm).map((section, sectionIndex) => (
                  <section className="form-section-card google-section-card" key={section.id}>
                    <div className="google-section-header">
                      <input
                        className="section-title-input"
                        value={section.title}
                        onChange={(event) =>
                          updateFormSection(section.id, {
                            title: event.target.value,
                          })
                        }
                      />
                      <button
                        type="button"
                        className="danger-lite"
                        disabled={getFormSections(activeForm).length <= 1}
                        onClick={() => deleteFormSection(section.id)}
                      >
                        Delete section
                      </button>
                    </div>

                    <textarea
                      className="section-description-input"
                      value={section.description || ""}
                      placeholder="Section description"
                      onChange={(event) =>
                        updateFormSection(section.id, {
                          description: event.target.value,
                        })
                      }
                    />

                    {(section.fields || []).map((field) => (
                      <article
                        className={`question-card google-question-card ${selected.id === field.id ? "active" : ""}`}
                        key={field.id}
                        onClick={() => setSelected({ type: "field", id: field.id })}
                      >
                        <div className="question-main">
                          <div className="google-question-topline">
                            <input
                              className="question-title-input"
                              value={field.label}
                              placeholder="Question"
                              onChange={(event) =>
                                updateFormField(field.id, {
                                  label: event.target.value,
                                })
                              }
                            />
                            <select
                              value={field.type}
                              onChange={(event) =>
                                updateFormField(field.id, {
                                  type: event.target.value,
                                })
                              }
                            >
                              {fieldTypes.map((type) => (
                                <option key={type.id} value={type.id}>{type.label}</option>
                              ))}
                            </select>
                          </div>

                          <div className="question-secondary-grid">
                            <input
                              value={field.helpText || ""}
                              placeholder="Help text shown under the question"
                              onChange={(event) =>
                                updateFormField(field.id, {
                                  helpText: event.target.value,
                                })
                              }
                            />
                            <input
                              value={field.placeholder || ""}
                              placeholder="Placeholder text"
                              onChange={(event) =>
                                updateFormField(field.id, {
                                  placeholder: event.target.value,
                                })
                              }
                            />
                            <input
                              value={field.defaultValue || ""}
                              placeholder="Default answer"
                              onChange={(event) =>
                                updateFormField(field.id, {
                                  defaultValue: event.target.value,
                                })
                              }
                            />
                          </div>

                          {["dropdown", "radio", "checkboxes", "status"].includes(field.type) && (
                            <textarea
                              className="options-editor"
                              value={(field.options || []).join("\n")}
                              placeholder="One option per line"
                              onChange={(event) =>
                                updateFormField(field.id, {
                                  options: splitLines(event.target.value),
                                })
                              }
                            />
                          )}

                          {field.type === "linearScale" && (
                            <div className="scale-editor">
                              <label>
                                From
                                <input
                                  type="number"
                                  min="0"
                                  max="10"
                                  value={field.scaleMin || 1}
                                  onChange={(event) =>
                                    updateFormField(field.id, {
                                      scaleMin: Number(event.target.value),
                                    })
                                  }
                                />
                              </label>
                              <label>
                                To
                                <input
                                  type="number"
                                  min="2"
                                  max="10"
                                  value={field.scaleMax || 5}
                                  onChange={(event) =>
                                    updateFormField(field.id, {
                                      scaleMax: Number(event.target.value),
                                    })
                                  }
                                />
                              </label>
                              <label>
                                Low label
                                <input
                                  value={field.scaleMinLabel || ""}
                                  onChange={(event) =>
                                    updateFormField(field.id, {
                                      scaleMinLabel: event.target.value,
                                    })
                                  }
                                />
                              </label>
                              <label>
                                High label
                                <input
                                  value={field.scaleMaxLabel || ""}
                                  onChange={(event) =>
                                    updateFormField(field.id, {
                                      scaleMaxLabel: event.target.value,
                                    })
                                  }
                                />
                              </label>
                            </div>
                          )}

                          {field.type === "rating" && (
                            <label className="inline-setting">
                              Max rating
                              <input
                                type="number"
                                min="2"
                                max="10"
                                value={field.maxRating || 5}
                                onChange={(event) =>
                                  updateFormField(field.id, {
                                    maxRating: Number(event.target.value),
                                  })
                                }
                              />
                            </label>
                          )}

                          {activeForm.mode === "quiz" && (
                            <div className="quiz-question-settings">
                              {renderQuizAnswerKeyEditor(field)}
                              <label>
                                Question time override (seconds)
                                <input
                                  type="number"
                                  min="0"
                                  value={Number(field.quizTimeLimitSec || 0)}
                                  placeholder="Use default"
                                  onChange={(event) =>
                                    updateFormField(field.id, {
                                      quizTimeLimitSec: Math.max(0, Number(event.target.value || 0)),
                                    })
                                  }
                                />
                              </label>
                            </div>
                          )}
                        </div>

                        <div className="question-footer-actions">
                          <span>
                            Question {sectionIndex + 1}.
                            {(section.fields || []).findIndex((item) => item.id === field.id) + 1}
                          </span>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              moveFormField(field.id, "up");
                            }}
                          >
                            Up
                          </button>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              moveFormField(field.id, "down");
                            }}
                          >
                            Down
                          </button>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              duplicateFormField(field.id);
                            }}
                          >
                            Duplicate
                          </button>
                          <label className="checkbox-control">
                            <input
                              type="checkbox"
                              checked={field.required}
                              onChange={(event) =>
                                updateFormField(field.id, {
                                  required: event.target.checked,
                                })
                              }
                            />
                            Required
                          </label>
                          <button
                            type="button"
                            className="danger-lite"
                            onClick={(event) => {
                              event.stopPropagation();
                              deleteFormField(field.id);
                            }}
                          >
                            Delete
                          </button>
                        </div>
                      </article>
                    ))}

                    <button
                      type="button"
                      className="add-question-wide"
                      onClick={() => addFieldToForm("shortText", section.id)}
                    >
                      + Add question
                    </button>
                  </section>
                ))}
              </div>
            </>
          )}
        </main>
      </div>

      {quizOptionsOpen && (
        <div className="quiz-drawer-backdrop" onClick={() => setQuizOptionsOpen(false)}>
          <aside
            className="quiz-options-drawer"
            aria-label="Quiz options"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="quiz-drawer-header">
              <div>
                <span>Quiz features</span>
                <h3>Quiz Options</h3>
                <p>Control timing, focus mode, scoring, results, and retakes for this form.</p>
              </div>
              <button type="button" onClick={() => setQuizOptionsOpen(false)}>Close</button>
            </div>

            <div className="quiz-settings-grid quiz-drawer-grid">
              <label className="checkbox-control">
                <input
                  type="checkbox"
                  checked={activeForm?.mode === "quiz"}
                  onChange={(event) =>
                    updateActiveForm((form) => ({
                      ...form,
                      mode: event.target.checked ? "quiz" : "form",
                      quiz: getQuizSettings(form),
                    }))
                  }
                />
                Enable quiz mode
              </label>

              <label className="checkbox-control">
                <input
                  type="checkbox"
                  checked={Boolean(getQuizSettings(activeForm).lockScreen)}
                  onChange={(event) => updateActiveFormQuiz({ lockScreen: event.target.checked })}
                />
                Lock screen in focus mode
              </label>

              <label>
                Total time limit (minutes)
                <input
                  type="number"
                  min="0"
                  value={Math.round(Number(getQuizSettings(activeForm).totalTimeLimitSec || 0) / 60)}
                  onChange={(event) =>
                    updateActiveFormQuiz({
                      totalTimeLimitSec: Math.max(0, Number(event.target.value || 0) * 60),
                    })
                  }
                />
              </label>

              <label>
                Default time per question (seconds)
                <input
                  type="number"
                  min="0"
                  value={Number(getQuizSettings(activeForm).questionTimeLimitSec || 0)}
                  onChange={(event) =>
                    updateActiveFormQuiz({
                      questionTimeLimitSec: Math.max(0, Number(event.target.value || 0)),
                    })
                  }
                />
              </label>

              <label>
                Scoring
                <select
                  value={getQuizSettings(activeForm).scoring}
                  onChange={(event) => updateActiveFormQuiz({ scoring: event.target.value })}
                >
                  <option value="automatic">Automatic</option>
                  <option value="manual">Manual review</option>
                  <option value="completion">Completion only</option>
                </select>
              </label>

              <label>
                Required passing score (%)
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={Number(getQuizSettings(activeForm).passingScore || 0)}
                  onChange={(event) =>
                    updateActiveFormQuiz({
                      passingScore: Math.min(100, Math.max(0, Number(event.target.value || 0))),
                    })
                  }
                />
              </label>

              <label className="checkbox-control">
                <input
                  type="checkbox"
                  checked={Boolean(getQuizSettings(activeForm).showResults)}
                  onChange={(event) => updateActiveFormQuiz({ showResults: event.target.checked })}
                />
                Show results after submit
              </label>

              <label className="checkbox-control">
                <input
                  type="checkbox"
                  checked={Boolean(getQuizSettings(activeForm).allowRetakes)}
                  onChange={(event) => updateActiveFormQuiz({ allowRetakes: event.target.checked })}
                />
                Allow retakes
              </label>

              <label>
                Max retakes
                <input
                  type="number"
                  min="0"
                  value={Number(getQuizSettings(activeForm).maxRetakes || 0)}
                  onChange={(event) =>
                    updateActiveFormQuiz({
                      maxRetakes: Math.max(0, Number(event.target.value || 0)),
                    })
                  }
                />
              </label>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}
