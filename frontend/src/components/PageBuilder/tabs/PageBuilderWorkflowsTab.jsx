export default function PageBuilderWorkflowsTab({
  project,
  activeWorkflow,
  workflowStepTypes,
  selectWorkflow,
  addWorkflow,
  addWorkflowStep,
  updateActiveWorkflow,
  updateWorkflowStep,
  deleteWorkflowStep,
}) {
  return (
    <div className="workspace-page">
      <div className="workspace-header">
        <div>
          <h2>Workflows</h2>
          <p>Front-end workflow prototypes. These describe what backend automation should do later.</p>
        </div>

        <button type="button" onClick={addWorkflow}>
          + Workflow
        </button>
      </div>

      <div className="forms-layout">
        <aside className="object-list">
          {project.workflows.map((workflow) => (
            <button
              key={workflow.id}
              type="button"
              className={activeWorkflow?.id === workflow.id ? "active" : ""}
              onClick={() => selectWorkflow(workflow.id)}
            >
              <strong>{workflow.name}</strong>
              <span>
                {workflow.enabled ? "Enabled" : "Disabled"} / {workflow.steps.length} steps
              </span>
            </button>
          ))}
        </aside>

        <section className="form-editor">
          {activeWorkflow && (
            <>
              <div className="editor-card-header">
                <h3>{activeWorkflow.name}</h3>
                <button type="button" onClick={addWorkflowStep}>
                  + Step
                </button>
              </div>

              <label>
                Workflow name
                <input
                  value={activeWorkflow.name}
                  onChange={(event) =>
                    updateActiveWorkflow((workflow) => ({
                      ...workflow,
                      name: event.target.value,
                    }))
                  }
                />
              </label>

              <label>
                Connected form
                <select
                  value={activeWorkflow.formId || ""}
                  onChange={(event) =>
                    updateActiveWorkflow((workflow) => ({
                      ...workflow,
                      formId: event.target.value,
                    }))
                  }
                >
                  {project.forms.map((form) => (
                    <option key={form.id} value={form.id}>
                      {form.title}
                    </option>
                  ))}
                </select>
              </label>

              <label className="checkbox-control">
                <input
                  type="checkbox"
                  checked={activeWorkflow.enabled}
                  onChange={(event) =>
                    updateActiveWorkflow((workflow) => ({
                      ...workflow,
                      enabled: event.target.checked,
                    }))
                  }
                />
                Enabled
              </label>

              <div className="automations-grid">
                {activeWorkflow.steps.map((step, index) => (
                  <div className="automation-card" key={step.id}>
                    <div className="automation-card-header">
                      <strong>Step {index + 1}</strong>
                      <button
                        type="button"
                        className="danger-lite"
                        onClick={() => deleteWorkflowStep(step.id)}
                      >
                        Delete
                      </button>
                    </div>

                    <label>
                      Type
                      <select
                        value={step.type}
                        onChange={(event) =>
                          updateWorkflowStep(step.id, { type: event.target.value })
                        }
                      >
                        {workflowStepTypes.map((type) => (
                          <option key={type.id} value={type.id}>
                            {type.label}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label>
                      Label
                      <input
                        value={step.label}
                        onChange={(event) =>
                          updateWorkflowStep(step.id, { label: event.target.value })
                        }
                      />
                    </label>

                    <label>
                      Details
                      <textarea
                        value={step.details}
                        onChange={(event) =>
                          updateWorkflowStep(step.id, { details: event.target.value })
                        }
                      />
                    </label>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}