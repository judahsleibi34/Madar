import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ArrowLeft, ArrowRight, X } from 'lucide-react';

import { uiText } from './constants/uiText';
import { analysisGroups } from './constants/analysisConfig';
import { API_URL, getFriendlyExternalError, readApiResponse } from './utils/api';
import { cleanObject, escapeCsvValue } from './utils/formatters';
import { getMissingRequiredParams } from './utils/validation';

import Stepper from './components/Stepper';
import DataSourceStep from './components/DataSourceStep';
import DatasetReviewStep from './components/DatasetReviewStep';
import PrepareDataStep from './components/PrepareDataStep';
import ReportBuilderStep from './components/ReportBuilderStep';
import AssistantPanel from './components/AssistantPanel';
import ReportCanvas from './components/ReportCanvas';

export default function DataAnalysisWorkspace({
  lang = "en",
  project,
  getFormFields = () => [],
  selectForm,
  setActiveTab,
}) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const isArabic = activeLang === "ar";
  const t = uiText[activeLang];

  const availableForms = project?.forms || [];
  const firstFormWithResponses =
    availableForms.find((form) => form.responses?.length) || availableForms[0];

  const [currentStep, setCurrentStep] = useState("source");
  const [sourceMode, setSourceMode] = useState("forms");
  const [selectedFormId, setSelectedFormId] = useState(firstFormWithResponses?.id || "");
  const [dataset, setDataset] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [externalUrl, setExternalUrl] = useState("");
  const [inspection, setInspection] = useState(null);
  const [inspectionCache, setInspectionCache] = useState({});
  const [analysisResult, setAnalysisResult] = useState(null);
  const [assistQuestion, setAssistQuestion] = useState("");
  const [assistResult, setAssistResult] = useState(null);
  const [analysisError, setAnalysisError] = useState("");
  const [flowToast, setFlowToast] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [reportOptions, setReportOptions] = useState({
    title: "",
    includeSummary: true,
    includeKpis: true,
    includeInsights: true,
    includeTables: true,
    includeCharts: true,
    includeWarnings: true,
  });

  const [cleaning, setCleaning] = useState({
    trimText: true,
    lowercaseText: false,
    removeDuplicates: false,
    removeMissingRows: false,
    fillMissing: false,
    fillColumn: "",
    fillMethod: "mode",
    fillValue: "",
    removeOutliers: false,
    outlierColumns: [],
    dropColumns: [],
    convertColumn: "",
    convertType: "numeric",
    renameColumn: "",
    renameTo: "",
  });

  const [analysisDomain, setAnalysisDomain] = useState("finance");
  const [analysisMethod, setAnalysisMethod] = useState(
    analysisGroups.finance.methods[0].id
  );
  const [params, setParams] = useState({ ...analysisGroups.finance.methods[0].template });

  const selectedForm =
    availableForms.find((form) => form.id === selectedFormId) || firstFormWithResponses;

  const formFields = selectedForm ? getFormFields(selectedForm) : [];
  const methods = analysisGroups[analysisDomain].methods;
  const activeMethod =
    methods.find((method) => method.id === analysisMethod) || methods[0];

  const columns = useMemo(() => dataset?.columns || [], [dataset]);

  const numericColumns = useMemo(() => {
    const preview = dataset?.preview || [];
    return columns.filter((column) =>
      preview.some((row) => Number.isFinite(Number(row[column])))
    );
  }, [columns, dataset]);

  const textColumns = useMemo(
    () => columns.filter((column) => !numericColumns.includes(column)),
    [columns, numericColumns]
  );

  useEffect(() => {
    if (!flowToast) return undefined;

    const timeoutId = window.setTimeout(() => {
      setFlowToast("");
    }, 7000);

    return () => window.clearTimeout(timeoutId);
  }, [flowToast]);

  const showFlowError = (message) => {
    setAnalysisError(message);
    setFlowToast("");
    window.setTimeout(() => setFlowToast(message), 0);
  };

  const cleaningActions = useMemo(() => {
    const actions = [];

    if (cleaning.trimText && textColumns.length) {
      actions.push({
        type: "clean_text_columns",
        params: {
          columns: textColumns,
          lower: cleaning.lowercaseText,
          strip: true,
          collapse_spaces: true,
        },
      });
    }

    if (cleaning.removeDuplicates) {
      actions.push({ type: "drop_duplicates", params: {} });
    }

    if (cleaning.removeMissingRows) {
      actions.push({ type: "drop_missing_rows", params: { how: "any" } });
    }

    if (cleaning.fillMissing && cleaning.fillColumn) {
      const config = { method: cleaning.fillMethod };

      if (cleaning.fillMethod === "constant") {
        config.value = cleaning.fillValue;
      }

      actions.push({
        type: "fill_missing",
        params: { fill_map: { [cleaning.fillColumn]: config } },
      });
    }

    if (cleaning.removeOutliers && cleaning.outlierColumns.length) {
      actions.push({
        type: "remove_outliers_iqr",
        params: { columns: cleaning.outlierColumns, multiplier: 1.5 },
      });
    }

    if (cleaning.dropColumns.length) {
      actions.push({
        type: "drop_columns",
        params: { columns: cleaning.dropColumns },
      });
    }

    if (cleaning.convertColumn) {
      actions.push({
        type: "convert_column_types",
        params: { type_map: { [cleaning.convertColumn]: cleaning.convertType } },
      });
    }

    if (cleaning.renameColumn && cleaning.renameTo.trim()) {
      actions.push({
        type: "rename_column",
        params: { rename_map: { [cleaning.renameColumn]: cleaning.renameTo.trim() } },
      });
    }

    return actions;
  }, [cleaning, textColumns]);

  const updateCleaning = (key, value) => {
    setCleaning((current) => ({ ...current, [key]: value }));
  };

  const updateParams = (key, value) => {
    setParams((current) => ({ ...current, [key]: value }));
  };

  const updateReportOptions = (key, value) => {
    setReportOptions((current) => ({ ...current, [key]: value }));
  };

  const setDomain = (domain) => {
    const nextMethod = analysisGroups[domain].methods[0];

    setAnalysisDomain(domain);
    setAnalysisMethod(nextMethod.id);
    setParams({ ...nextMethod.template });
  };

  const setMethod = (methodId) => {
    const nextMethod = methods.find((method) => method.id === methodId) || methods[0];

    setAnalysisMethod(nextMethod.id);
    setParams({ ...nextMethod.template });
  };

  const setLoadedDataset = (data) => {
    setDataset(data);
    setInspection(null);
    setInspectionCache({});
    setAnalysisResult(null);
    setAssistResult(null);
    setCurrentStep("review");
  };

  const uploadFile = async (file) => {
    if (!file) {
      showFlowError(t.chooseFileFirst);
      return;
    }

    const payload = new FormData();
    payload.append("file", file);

    setIsLoading(true);
    setAnalysisError("");

    try {
      const response = await fetch(`${API_URL}/data/upload`, {
        method: "POST",
        credentials: "include",
        body: payload,
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        throw new Error(data.detail || "The data could not be loaded.");
      }

      setLoadedDataset(data);
    } catch (error) {
      showFlowError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const loadExternalSource = async () => {
    const inputPath = externalUrl.trim();

    if (!inputPath) {
      showFlowError(t.pasteLinkFirst);
      return;
    }

    setIsLoading(true);
    setAnalysisError("");

    try {
      const response = await fetch(`${API_URL}/data/read`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_path: inputPath }),
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        throw new Error(getFriendlyExternalError(data.detail));
      }

      setLoadedDataset({
        ...data,
        file_path: data.file_path || inputPath,
        original_filename: data.original_filename || inputPath,
      });
    } catch (error) {
      showFlowError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const importFormResponses = async () => {
    if (!selectedForm) {
      showFlowError(t.createFormFirst);
      return;
    }

    if (!selectedForm.responses?.length) {
      showFlowError(t.emptyForm);
      return;
    }

    const headers = [
      "Submitted at",
      "Status",
      ...formFields.map((field) => field.label || field.title || field.id),
    ];

    const rows = selectedForm.responses.map((response) => [
      response.createdAt || "",
      response.status || "Submitted",
      ...formFields.map((field) => response.answers?.[field.id] ?? ""),
    ]);

    const csv = [headers, ...rows]
      .map((row) => row.map(escapeCsvValue).join(","))
      .join("\n");

    const file = new File(
      ["\uFEFF" + csv],
      `${selectedForm.title || "form-responses"}.csv`,
      { type: "text/csv;charset=utf-8" }
    );

    await uploadFile(file);
  };

  const runInspection = async (type) => {
    if (!dataset?.file_path) {
      showFlowError(t.loadDataBeforeReview);
      return;
    }

    const cacheKey = `${dataset.file_path}:${type}`;
    if (inspectionCache[cacheKey]) {
      setInspection(inspectionCache[cacheKey]);
      setAnalysisError("");
      return;
    }

    const paths = {
      overview: "/cleaning/inspect",
      statistics: "/cleaning/statistics",
      missing: "/cleaning/missing-report",
      quality: "/cleaning/quality-report",
    };

    setIsLoading(true);
    setAnalysisError("");

    try {
      const response = await fetch(`${API_URL}${paths[type]}`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_path: dataset.file_path }),
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        throw new Error(data.detail || "The review could not be completed.");
      }

      const nextInspection = { type, data };
      setInspection(nextInspection);
      setInspectionCache((current) => ({ ...current, [cacheKey]: nextInspection }));
    } catch (error) {
      showFlowError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const runAnalysis = async () => {
    if (!dataset?.file_path) {
      showFlowError(t.loadDataBeforeAnalysis);
      return;
    }

    const missingRequiredParams = getMissingRequiredParams(
      activeMethod.template,
      params,
      activeLang
    );

    if (missingRequiredParams.length) {
      showFlowError(t.missingRequiredFields(missingRequiredParams));
      setCurrentStep("report");
      return;
    }

    setIsLoading(true);
    setAnalysisError("");

    try {
      const response = await fetch(`${API_URL}/analysis/run`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_path: dataset.file_path,
          cleaning_actions: cleaningActions,
          language: activeLang,
          symbols: {
            currency: activeLang === "ar" ? "د.إ" : "$",
            percent: activeLang === "ar" ? "٪" : "%",
            decimal_separator: activeLang === "ar" ? "," : ".",
            thousands_separator: activeLang === "ar" ? "." : ",",
          },
          analysis_requests: [
            {
              domain: analysisDomain,
              method: analysisMethod,
              key: activeMethod.label,
              params: cleanObject(params),
            },
          ],
        }),
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        throw new Error(data.detail || "The analysis could not be completed.");
      }

      setAnalysisResult(data);
      setCurrentStep("report");
    } catch (error) {
      showFlowError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const runAssistedQuestion = async () => {
    const question = assistQuestion.trim();

    if (!dataset?.file_path) {
      showFlowError(t.loadDataBeforeAnalysis);
      return;
    }

    if (!question) {
      showFlowError(t.writeQuestionFirst);
      return;
    }

    setIsLoading(true);
    setAnalysisError("");

    try {
      const response = await fetch(`${API_URL}/analysis/assist`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_path: dataset.file_path,
          cleaning_actions: cleaningActions,
          question,
          language: activeLang,
          symbols: {
            currency: activeLang === "ar" ? "د.إ" : "$",
            percent: activeLang === "ar" ? "٪" : "%",
            decimal_separator: activeLang === "ar" ? "," : ".",
            thousands_separator: activeLang === "ar" ? "." : ",",
          },
        }),
      });

      const data = await readApiResponse(response);

      if (!response.ok) {
        throw new Error(data.detail || "The assisted analysis could not be completed.");
      }

      setAssistResult(data.result || data);
      setAssistQuestion("");
    } catch (error) {
      showFlowError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const analysisPayload = useMemo(() => {
    if (!analysisResult?.results) return analysisResult;

    return (
      analysisResult.results[activeMethod.label] ||
      Object.values(analysisResult.results)[0] ||
      analysisResult.results
    );
  }, [analysisResult, activeMethod.label]);

  const goToPreviousStep = () => {
    const order = ["source", "review", "prepare", "report"];
    const currentIndex = order.indexOf(currentStep);
    setCurrentStep(order[Math.max(0, currentIndex - 1)]);
  };

  const goToNextStep = () => {
    const order = ["source", "review", "prepare", "report"];
    const currentIndex = order.indexOf(currentStep);
    setCurrentStep(order[Math.min(order.length - 1, currentIndex + 1)]);
  };

  const renderCurrentStep = () => {
    if (currentStep === "source") {
      return (
        <DataSourceStep
          sourceMode={sourceMode}
          setSourceMode={setSourceMode}
          availableForms={availableForms}
          selectedForm={selectedForm}
          setSelectedFormId={setSelectedFormId}
          selectedFile={selectedFile}
          setSelectedFile={setSelectedFile}
          externalUrl={externalUrl}
          setExternalUrl={setExternalUrl}
          importFormResponses={importFormResponses}
          uploadFile={uploadFile}
          loadExternalSource={loadExternalSource}
          selectForm={selectForm}
          setActiveTab={setActiveTab}
          isLoading={isLoading}
          t={t}
        />
      );
    }

    if (currentStep === "review") {
      return (
        <DatasetReviewStep
          dataset={dataset}
          inspection={inspection}
          runInspection={runInspection}
          isLoading={isLoading}
          t={t}
        />
      );
    }

    if (currentStep === "prepare") {
      return (
        <PrepareDataStep
          dataset={dataset}
          columns={columns}
          numericColumns={numericColumns}
          cleaning={cleaning}
          updateCleaning={updateCleaning}
          t={t}
        />
      );
    }

    return (
      <ReportBuilderStep
        dataset={dataset}
        activeLang={activeLang}
        analysisDomain={analysisDomain}
        setDomain={setDomain}
        methods={methods}
        analysisMethod={analysisMethod}
        setMethod={setMethod}
        activeMethod={activeMethod}
        params={params}
        updateParams={updateParams}
        columns={columns}
        numericColumns={numericColumns}
        runAnalysis={runAnalysis}
        isLoading={isLoading}
        reportOptions={reportOptions}
        updateReportOptions={updateReportOptions}
        t={t}
      />
    );
  };

  return (
    <div className="daw-page" dir={isArabic ? "rtl" : "ltr"}>
      <header className="daw-header">
        <div>
          <span className="daw-kicker">{t.kicker}</span>
          <h2>{t.title}</h2>
          <p>{t.subtitle}</p>
        </div>
      </header>

      <Stepper
        currentStep={currentStep}
        setCurrentStep={setCurrentStep}
        dataset={dataset}
        t={t}
      />

      {flowToast ? (
        <div className="daw-flow-toast" role="alert" aria-live="assertive">
          <span>
            <AlertTriangle size={18} />
          </span>
          <div>
            <strong>{t.flowIssueTitle}</strong>
            <p>{flowToast}</p>
          </div>
          <button type="button" aria-label="Dismiss message" onClick={() => setFlowToast("")}>
            <X size={16} />
          </button>
        </div>
      ) : null}

      {analysisError ? <div className="daw-error">{analysisError}</div> : null}

      <section className={`daw-layout daw-step-${currentStep}`}>
        <main className="daw-flow">
          <div className="daw-step-content">
            {renderCurrentStep()}

            {currentStep === "report" ? (
              <aside className="daw-canvas-column">
                <ReportCanvas
                  dataset={dataset}
                  analysisResult={analysisResult}
                  analysisPayload={analysisPayload}
                  activeMethod={activeMethod}
                  activeLang={activeLang}
                  reportOptions={reportOptions}
                  t={t}
                />
              </aside>
            ) : null}
          </div>

          <AssistantPanel
            dataset={dataset}
            assistQuestion={assistQuestion}
            setAssistQuestion={setAssistQuestion}
            runAssistedQuestion={runAssistedQuestion}
            assistResult={assistResult}
            isLoading={isLoading}
            t={t}
          />

          {dataset ? (
            <div className={`daw-flow-actions ${currentStep === "source" ? "only-next" : ""}`}>
              {currentStep !== "source" ? (
                <button type="button" className="daw-step-back" onClick={goToPreviousStep}>
                  {isArabic ? <ArrowRight size={16} /> : <ArrowLeft size={16} />}
                  {t.back}
                </button>
              ) : null}

              {currentStep !== "report" ? (
                <button type="button" className="daw-primary daw-step-next" onClick={goToNextStep}>
                  {t.continue}
                  {isArabic ? <ArrowLeft size={16} /> : <ArrowRight size={16} />}
                </button>
              ) : null}
            </div>
          ) : null}
        </main>
      </section>
    </div>
  );
}
