export default function Stepper({
  currentStep,
  setCurrentStep,
  dataset,
  metricsReady = false,
  onLockedStep,
  t,
}) {
  const steps = [
    { id: "source", label: t.source, enabled: true },
    { id: "review", label: t.review, enabled: Boolean(dataset) },
    { id: "prepare", label: t.prepare, enabled: Boolean(dataset) },
    { id: "visualization", label: t.visualization, enabled: Boolean(dataset), requiresMetrics: true },
    { id: "report", label: t.report, enabled: Boolean(dataset), requiresMetrics: true },
  ];

  return (
    <nav className="daw-stepper" aria-label={t.stepsLabel || "Data analysis steps"}>
      {steps.map((step, index) => (
        <button
          key={step.id}
          type="button"
          className={`${currentStep === step.id ? "active" : ""} ${
            step.requiresMetrics && !metricsReady ? "locked" : ""
          }`.trim()}
          disabled={!step.enabled}
          aria-disabled={step.requiresMetrics && !metricsReady}
          title={
            step.requiresMetrics && !metricsReady
              ? "Generate metrics in Prepare before opening this step"
              : undefined
          }
          onClick={() => {
            if (step.requiresMetrics && !metricsReady) {
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
