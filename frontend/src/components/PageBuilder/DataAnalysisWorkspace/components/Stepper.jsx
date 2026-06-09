export default function Stepper({ currentStep, setCurrentStep, dataset, t }) {
  const steps = [
    { id: "source", label: t.source, enabled: true },
    { id: "review", label: t.review, enabled: Boolean(dataset) },
    { id: "prepare", label: t.prepare, enabled: Boolean(dataset) },
    { id: "visualization", label: t.visualization, enabled: Boolean(dataset) },
    { id: "report", label: t.report, enabled: Boolean(dataset) },
  ];

  return (
    <nav className="daw-stepper" aria-label={t.stepsLabel || "Data analysis steps"}>
      {steps.map((step, index) => (
        <button
          key={step.id}
          type="button"
          className={currentStep === step.id ? "active" : ""}
          disabled={!step.enabled}
          onClick={() => setCurrentStep(step.id)}
        >
          <span>{index + 1}</span>
          <strong>{step.label}</strong>
        </button>
      ))}
    </nav>
  );
}
