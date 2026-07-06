export default function Stepper({
  currentStep,
  setCurrentStep,
  dataset,
  dataframesSaved = false,
  onLockedStep,
  t,
}) {
  const steps = [
    { id: "source", label: t.source, enabled: true },
    { id: "review", label: t.review, enabled: Boolean(dataset) },
    { id: "prepare", label: t.prepare, enabled: Boolean(dataset) },
    { id: "visualization", label: t.visualization, enabled: Boolean(dataset), requiresSavedData: true },
    { id: "report", label: t.report, enabled: Boolean(dataset), requiresSavedData: true },
  ];

  return (
    <nav className="daw-stepper" aria-label={t.stepsLabel || "Data analysis steps"}>
      {steps.map((step, index) => (
        <button
          key={step.id}
          type="button"
          className={`${currentStep === step.id ? "active" : ""} ${
            step.requiresSavedData && !dataframesSaved ? "locked" : ""
          }`.trim()}
          disabled={!step.enabled}
          aria-disabled={step.requiresSavedData && !dataframesSaved}
          title={
            step.requiresSavedData && !dataframesSaved
              ? t.saveDataframesFirst || "Save dataframes in Prepare before opening this step"
              : undefined
          }
          onClick={() => {
            if (step.requiresSavedData && !dataframesSaved) {
              onLockedStep?.(step.id);
              return;
            }
            setCurrentStep(step.id);
          }}
        >
          <span>{index + 1}</span>
          <strong>{step.label}</strong>
        </button>
      ))}
    </nav>
  );
}
