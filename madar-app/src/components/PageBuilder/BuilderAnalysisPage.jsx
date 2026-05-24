import { useMemo, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const analysisGroups = {
  finance: {
    label: "Finance",
    description: "Revenue, cost, budget, donor funding, and transaction summaries.",
    methods: [
      { id: "profit_loss_summary", label: "Profit and loss summary", template: { revenue_column: "", cost_column: "" } },
      { id: "add_profit_column", label: "Add profit column", template: { revenue_column: "", cost_column: "", profit_column: "profit" } },
      { id: "budget_vs_actual", label: "Budget vs actual", template: { budget_column: "", actual_column: "", group_column: "" } },
      { id: "expense_summary", label: "Expense summary", template: { expense_column: "", category_column: "" } },
      { id: "revenue_by_group", label: "Revenue by group", template: { revenue_column: "", group_column: "" } },
      { id: "monthly_summary", label: "Monthly summary", template: { date_column: "", value_columns: [] } },
      { id: "daily_summary", label: "Daily summary", template: { date_column: "", value_columns: [] } },
      { id: "cash_flow_summary", label: "Cash flow summary", template: { inflow_column: "", outflow_column: "" } },
      { id: "top_expenses", label: "Top expenses", template: { expense_column: "", rows: 10 } },
      { id: "financial_ratios", label: "Financial ratios", template: { revenue_column: "", cost_column: "", expense_column: "" } },
      { id: "detect_negative_values", label: "Negative value check", template: { columns: [] } },
      { id: "transaction_summary", label: "Transaction summary", template: { amount_column: "", transaction_id_column: "" } },
      { id: "cost_per_beneficiary", label: "Cost per beneficiary", template: { cost_column: "", beneficiary_column: "", group_column: "" } },
      { id: "donor_funding_summary", label: "Donor funding summary", template: { donor_column: "", amount_column: "" } },
    ],
  },
  meal: {
    label: "MEAL",
    description: "Department, meal, quantity, price, and revenue analysis.",
    methods: [
      { id: "department_summary", label: "Department summary", template: { department_column: "", numeric_columns: [] } },
      { id: "top_meals", label: "Top meals", template: { meal_column: "", value_column: "", rows: 10 } },
      { id: "average_price_by_department", label: "Average price by department", template: { department_column: "", price_column: "" } },
      { id: "meal_counts", label: "Meal counts", template: { column: "" } },
      { id: "revenue_by_meal", label: "Revenue by meal", template: { meal_column: "", revenue_column: "" } },
      { id: "quantity_by_department", label: "Quantity by department", template: { department_column: "", quantity_column: "" } },
    ],
  },
  ngo_meal: {
    label: "NGO MEAL",
    description: "Program progress, beneficiary, activity, survey, and case analysis.",
    methods: [
      { id: "indicator_progress", label: "Indicator progress", template: { indicator_column: "", actual_column: "", target_column: "", group_column: "" } },
      { id: "target_achievement", label: "Target achievement", template: { actual_column: "", target_column: "" } },
      { id: "beneficiary_summary", label: "Beneficiary summary", template: { beneficiary_column: "", group_columns: [] } },
      { id: "disaggregation_summary", label: "Disaggregation summary", template: { value_column: "", disaggregation_columns: [] } },
      { id: "baseline_endline_change", label: "Baseline to endline change", template: { group_column: "", baseline_column: "", endline_column: "" } },
      { id: "activity_completion_rate", label: "Activity completion rate", template: { completed_column: "", planned_column: "", group_column: "" } },
      { id: "survey_question_summary", label: "Survey question summary", template: { question_column: "", response_column: "" } },
      { id: "location_summary", label: "Location summary", template: { location_column: "", value_columns: [] } },
      { id: "partner_summary", label: "Partner summary", template: { partner_column: "", value_columns: [] } },
      { id: "vulnerability_summary", label: "Vulnerability summary", template: { vulnerability_column: "", beneficiary_column: "" } },
      { id: "complaint_feedback_summary", label: "Complaint and feedback summary", template: { channel_column: "", status_column: "" } },
      { id: "case_status_summary", label: "Case status summary", template: { status_column: "", group_column: "" } },
      { id: "attendance_rate", label: "Attendance rate", template: { attended_column: "", registered_column: "", group_column: "" } },
    ],
  },
};

const formatJson = (value) => JSON.stringify(value, null, 2);

const compactParams = (params) =>
  Object.fromEntries(
    Object.entries(params).filter(([, value]) => {
      if (value === "" || value === null || value === undefined) return false;
      if (Array.isArray(value) && value.length === 0) return false;
      return true;
    })
  );

const toLabel = (key) =>
  key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .replace(/\bNgo\b/g, "NGO");

const displayValue = (value) => {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isInteger(value) ? value : Number(value.toFixed(3));
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return formatJson(value);
  return String(value);
};

const escapeCsvValue = (value) => {
  const text = Array.isArray(value) ? value.join("; ") : String(value ?? "");
  return `"${text.replace(/"/g, '""')}"`;
};

const pickAnalysisPayload = (result, methodLabel) => {
  if (!result || typeof result !== "object") return result;
  if (result.results && typeof result.results === "object") {
    return result.results[methodLabel] ?? Object.values(result.results)[0] ?? result.results;
  }
  return result;
};

const getFriendlyInspectionTitle = (type) => {
  if (type === "overview") return "Data overview";
  if (type === "statistics") return "Column statistics";
  if (type === "missing") return "Missing values";
  if (type === "quality") return "Data quality";
  return "Inspection";
};

const getFriendlyExternalError = (detail) => {
  const message = String(detail || "");
  const lowerMessage = message.toLowerCase();

  if (lowerMessage.includes("google sheet") || lowerMessage.includes("google returned")) {
    return message.replace(/^Failed to read data:\s*/i, "");
  }

  if (lowerMessage.includes("http error 400") || lowerMessage.includes("bad request")) {
    return "The link could not be read. For Google Sheets, share it with anyone who has the link or publish it to the web, then paste the full sheet URL.";
  }

  if (lowerMessage.includes("could not detect data format")) {
    return "The link was reachable, but it does not look like CSV, Excel, JSON, or Google Sheets data.";
  }

  return message || "The external data could not be loaded.";
};

const readApiResponse = async (response) => {
  const contentType = response.headers.get("Content-Type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();
  return {
    detail: text || response.statusText || "The server returned an unreadable response.",
  };
};

function ResultView({ value }) {
  if (!value) {
    return (
      <div className="analytics-empty compact">
        <strong>No result yet</strong>
        <p>Choose a data source and run an analysis.</p>
      </div>
    );
  }

  if (Array.isArray(value) && value.every((item) => item && typeof item === "object" && !Array.isArray(item))) {
    const columns = Array.from(new Set(value.flatMap((row) => Object.keys(row))));
    return (
      <div className="results-table-wrap">
        <table className="results-data-table">
          <thead>
            <tr>{columns.map((column) => <th key={column}>{toLabel(column)}</th>)}</tr>
          </thead>
          <tbody>
            {value.map((row, index) => (
              <tr key={`result_${index}`}>
                {columns.map((column) => <td key={column}>{displayValue(row[column])}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (value && typeof value === "object" && !Array.isArray(value)) {
    return (
      <div className="analysis-result-grid">
        {Object.entries(value).map(([key, item]) => (
          <article key={key}>
            <span>{toLabel(key)}</span>
            <strong>{displayValue(item)}</strong>
          </article>
        ))}
      </div>
    );
  }

  return <pre className="analysis-json-output friendly">{displayValue(value)}</pre>;
}

function ColumnSelect({ label, value, columns, optional, onChange }) {
  return (
    <label className="analysis-field">
      <span>{label}</span>
      <select value={value || ""} onChange={(event) => onChange(event.target.value)}>
        <option value="">{optional ? "No grouping" : "Select column"}</option>
        {columns.map((column) => <option key={column} value={column}>{column}</option>)}
      </select>
    </label>
  );
}

function MultiColumnSelect({ label, value, columns, onChange }) {
  const selected = Array.isArray(value) ? value : [];
  const toggleColumn = (column) => {
    onChange(selected.includes(column) ? selected.filter((item) => item !== column) : [...selected, column]);
  };

  return (
    <div className="analysis-field wide">
      <span>{label}</span>
      <div className="analysis-column-picker">
        {columns.length ? columns.map((column) => (
          <label key={column}>
            <input type="checkbox" checked={selected.includes(column)} onChange={() => toggleColumn(column)} />
            <span>{column}</span>
          </label>
        )) : <em>Load data to choose columns.</em>}
      </div>
    </div>
  );
}

export default function BuilderAnalysisPage({
  project,
  getFormFields = () => [],
  selectForm,
  setActiveTab,
}) {
  const availableForms = project?.forms || [];
  const firstFormWithResponses = availableForms.find((form) => form.responses?.length) || availableForms[0];

  const [sourceMode, setSourceMode] = useState("forms");
  const [selectedFormId, setSelectedFormId] = useState(firstFormWithResponses?.id || "");
  const [dataset, setDataset] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [externalUrl, setExternalUrl] = useState("");
  const [inspection, setInspection] = useState(null);
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
  const [analysisMethod, setAnalysisMethod] = useState(analysisGroups.finance.methods[0].id);
  const [params, setParams] = useState(analysisGroups.finance.methods[0].template);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analysisError, setAnalysisError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const selectedForm = availableForms.find((form) => form.id === selectedFormId) || firstFormWithResponses;
  const formFields = selectedForm ? getFormFields(selectedForm) : [];
  const methods = analysisGroups[analysisDomain].methods;
  const activeMethod = methods.find((method) => method.id === analysisMethod) || methods[0];
  const columns = useMemo(() => dataset?.columns || [], [dataset]);
  const numericColumnGuess = useMemo(() => {
    const preview = dataset?.preview || [];
    return columns.filter((column) => preview.some((row) => Number.isFinite(Number(row[column]))));
  }, [columns, dataset]);
  const textColumnGuess = useMemo(
    () => columns.filter((column) => !numericColumnGuess.includes(column)),
    [columns, numericColumnGuess]
  );

  const cleaningActions = useMemo(() => {
    const actions = [];
    if (cleaning.trimText && textColumnGuess.length) {
      actions.push({
        type: "clean_text_columns",
        params: { columns: textColumnGuess, lower: cleaning.lowercaseText, strip: true, collapse_spaces: true },
      });
    }
    if (cleaning.removeDuplicates) actions.push({ type: "drop_duplicates", params: {} });
    if (cleaning.removeMissingRows) actions.push({ type: "drop_missing_rows", params: { how: "any" } });
    if (cleaning.fillMissing && cleaning.fillColumn) {
      const config = { method: cleaning.fillMethod };
      if (cleaning.fillMethod === "constant") config.value = cleaning.fillValue;
      actions.push({ type: "fill_missing", params: { fill_map: { [cleaning.fillColumn]: config } } });
    }
    if (cleaning.removeOutliers && cleaning.outlierColumns.length) {
      actions.push({ type: "remove_outliers_iqr", params: { columns: cleaning.outlierColumns, multiplier: 1.5 } });
    }
    if (cleaning.dropColumns.length) {
      actions.push({ type: "drop_columns", params: { columns: cleaning.dropColumns } });
    }
    if (cleaning.convertColumn) {
      actions.push({ type: "convert_column_types", params: { type_map: { [cleaning.convertColumn]: cleaning.convertType } } });
    }
    if (cleaning.renameColumn && cleaning.renameTo.trim()) {
      actions.push({ type: "rename_column", params: { rename_map: { [cleaning.renameColumn]: cleaning.renameTo.trim() } } });
    }
    return actions;
  }, [cleaning, textColumnGuess]);

  const updateCleaning = (key, value) => setCleaning((current) => ({ ...current, [key]: value }));

  const updateParams = (key, value) => setParams((current) => ({ ...current, [key]: value }));

  const setDomain = (domain) => {
    const nextMethod = analysisGroups[domain].methods[0];
    setAnalysisDomain(domain);
    setAnalysisMethod(nextMethod.id);
    setParams(nextMethod.template);
  };

  const setMethod = (methodId) => {
    const nextMethod = methods.find((method) => method.id === methodId) || methods[0];
    setAnalysisMethod(nextMethod.id);
    setParams(nextMethod.template);
  };

  const uploadFile = async (file) => {
    if (!file) {
      setAnalysisError("Choose a file first.");
      return;
    }

    const payload = new FormData();
    payload.append("file", file);
    setIsLoading(true);
    setAnalysisError("");

    try {
      const response = await fetch(`${API_URL}/data/upload`, { method: "POST", body: payload });
      const data = await readApiResponse(response);
      if (!response.ok) throw new Error(data.detail || "The data could not be loaded.");
      setDataset(data);
      setInspection(null);
      setAnalysisResult(null);
    } catch (error) {
      setAnalysisError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const loadExternalSource = async () => {
    const inputPath = externalUrl.trim();
    if (!inputPath) {
      setAnalysisError("Paste a public data link or API URL first.");
      return;
    }

    setIsLoading(true);
    setAnalysisError("");

    try {
      const response = await fetch(`${API_URL}/data/read`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_path: inputPath }),
      });
      const data = await readApiResponse(response);
      if (!response.ok) throw new Error(getFriendlyExternalError(data.detail));
      setDataset({
        ...data,
        file_path: inputPath,
        original_filename: inputPath,
      });
      setInspection(null);
      setAnalysisResult(null);
    } catch (error) {
      setAnalysisError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const importFormResponses = async () => {
    if (!selectedForm) {
      setAnalysisError("Create a form before importing collected data.");
      return;
    }
    if (!selectedForm.responses?.length) {
      setAnalysisError("This form has no submitted responses yet.");
      return;
    }

    const headers = ["Submitted at", "Status", ...formFields.map((field) => field.label || field.title || field.id)];
    const rows = selectedForm.responses.map((response) => [
      response.createdAt || "",
      response.status || "Submitted",
      ...formFields.map((field) => response.answers?.[field.id] ?? ""),
    ]);
    const csv = [headers, ...rows].map((row) => row.map(escapeCsvValue).join(",")).join("\n");
    const file = new File([csv], `${selectedForm.title || "form-responses"}.csv`, { type: "text/csv" });
    await uploadFile(file);
  };

  const runInspection = async (type) => {
    if (!dataset?.file_path) {
      setAnalysisError("Load data before reviewing it.");
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
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ input_path: dataset.file_path }),
      });
      const data = await readApiResponse(response);
      if (!response.ok) throw new Error(data.detail || "The review could not be completed.");
      setInspection({ type, data });
    } catch (error) {
      setAnalysisError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const runAnalysis = async () => {
    if (!dataset?.file_path) {
      setAnalysisError("Load data before running analysis.");
      return;
    }

    setIsLoading(true);
    setAnalysisError("");

    try {
      const response = await fetch(`${API_URL}/analysis/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          input_path: dataset.file_path,
          cleaning_actions: cleaningActions,
          analysis_requests: [
            {
              domain: analysisDomain,
              method: analysisMethod,
              key: activeMethod.label,
              params: compactParams(params),
            },
          ],
        }),
      });
      const data = await readApiResponse(response);
      if (!response.ok) throw new Error(data.detail || "The analysis could not be completed.");
      setAnalysisResult(data);
    } catch (error) {
      setAnalysisError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const renderParamControl = ([key, value]) => {
    const label = toLabel(key);
    const optional = key.includes("group") || key.includes("category") || key.includes("expense_column") || key.includes("transaction_id");

    if (Array.isArray(value)) {
      return (
        <MultiColumnSelect
          key={key}
          label={label}
          value={value}
          columns={key.includes("numeric") || key.includes("value") ? numericColumnGuess : columns}
          onChange={(nextValue) => updateParams(key, nextValue)}
        />
      );
    }

    if (key === "rows") {
      return (
        <label key={key} className="analysis-field">
          <span>{label}</span>
          <input type="number" min="1" value={value} onChange={(event) => updateParams(key, Number(event.target.value || 1))} />
        </label>
      );
    }

    if (key.endsWith("_column") || key === "column") {
      return (
        <ColumnSelect
          key={key}
          label={label}
          value={value}
          columns={key.includes("amount") || key.includes("cost") || key.includes("revenue") || key.includes("actual") || key.includes("target") || key.includes("price") || key.includes("quantity") || key.includes("budget") || key.includes("baseline") || key.includes("endline") ? numericColumnGuess : columns}
          optional={optional}
          onChange={(nextValue) => updateParams(key, nextValue)}
        />
      );
    }

    return (
      <label key={key} className="analysis-field">
        <span>{label}</span>
        <input type="text" value={value || ""} onChange={(event) => updateParams(key, event.target.value)} />
      </label>
    );
  };

  const analysisPayload = pickAnalysisPayload(analysisResult, activeMethod.label);

  return (
    <div className="workspace-page analytics-dashboard-page analysis-runner-page">
      <div className="workspace-header analytics-header">
        <div>
          <span className="workspace-kicker">Data workspace</span>
          <h2>Analyze collected data</h2>
          <p>Import form responses or upload a spreadsheet, review the data, clean it, and run an analysis.</p>
        </div>
        <button type="button" className="primary-action" onClick={runAnalysis} disabled={isLoading || !dataset}>
          {isLoading ? "Working..." : "Run analysis"}
        </button>
      </div>

      {analysisError && <div className="analysis-error">{analysisError}</div>}

      <section className="analysis-source-panel analytics-card">
        <div className="analysis-source-tabs" role="tablist" aria-label="Choose data source">
          <button type="button" className={sourceMode === "forms" ? "active" : ""} onClick={() => setSourceMode("forms")}>
            Website form data
          </button>
          <button type="button" className={sourceMode === "upload" ? "active" : ""} onClick={() => setSourceMode("upload")}>
            Spreadsheet upload
          </button>
          <button type="button" className={sourceMode === "external" ? "active" : ""} onClick={() => setSourceMode("external")}>
            External link / API
          </button>
        </div>

        {sourceMode === "forms" ? (
          <div className="analysis-source-body">
            <div>
              <span className="workspace-kicker">From your website</span>
              <h3>Use collected form responses</h3>
              <p>Turn submitted website forms into a dataset for analysis.</p>
            </div>
            <label className="analysis-field">
              <span>Form</span>
              <select value={selectedForm?.id || ""} onChange={(event) => setSelectedFormId(event.target.value)}>
                {availableForms.map((form) => (
                  <option key={form.id} value={form.id}>
                    {form.title} ({form.responses?.length || 0} responses)
                  </option>
                ))}
              </select>
            </label>
            <div className="analysis-source-actions">
              <button type="button" className="primary-action" onClick={importFormResponses} disabled={isLoading || !selectedForm}>
                Import responses
              </button>
              <button
                type="button"
                onClick={() => {
                  if (selectedForm) selectForm?.(selectedForm.id);
                  setActiveTab?.("responses");
                }}
              >
                View responses
              </button>
            </div>
          </div>
        ) : sourceMode === "upload" ? (
          <div className="analysis-source-body">
            <div>
              <span className="workspace-kicker">From a file</span>
              <h3>Upload a spreadsheet</h3>
              <p>CSV, XLS, and XLSX files are supported.</p>
            </div>
            <label
              className="analysis-file-dropzone"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                event.preventDefault();
                setSelectedFile(event.dataTransfer.files?.[0] || null);
              }}
            >
              <input
                type="file"
                accept=".csv,.xls,.xlsx"
                onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
              />
              <strong>{selectedFile ? selectedFile.name : "Choose file or drop it here"}</strong>
              <span>{selectedFile ? "Ready to load" : "Use a spreadsheet exported from your tools"}</span>
            </label>
            <div className="analysis-source-actions">
              <button type="button" className="primary-action" onClick={() => uploadFile(selectedFile)} disabled={isLoading || !selectedFile}>
                Load file
              </button>
            </div>
          </div>
        ) : (
          <div className="analysis-source-body">
            <div>
              <span className="workspace-kicker">From another system</span>
              <h3>Connect a public data link</h3>
              <p>Use CSV, Excel, JSON API, or a published Google Sheet.</p>
            </div>
            <label className="analysis-field">
              <span>Data link</span>
              <input
                type="url"
                value={externalUrl}
                placeholder="https://example.com/data.csv"
                onChange={(event) => setExternalUrl(event.target.value)}
              />
              <small>Google Sheets must be shared publicly or published to the web.</small>
            </label>
            <div className="analysis-source-actions">
              <button type="button" className="primary-action" onClick={loadExternalSource} disabled={isLoading || !externalUrl.trim()}>
                Load link
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="analysis-dashboard-grid">
        <article className="analytics-card analysis-preview-card">
          <div className="analytics-card-header">
            <div>
              <span className="workspace-kicker">Preview</span>
              <h3>{dataset?.original_filename || "No data loaded"}</h3>
              <p>{dataset ? `${dataset.rows} rows and ${dataset.columns.length} columns are ready.` : "Choose form responses or upload a spreadsheet."}</p>
            </div>
          </div>

          {dataset ? (
            <>
              <div className="analysis-column-list">
                {columns.map((column) => (
                  <span key={column} className={numericColumnGuess.includes(column) ? "numeric" : ""}>{column}</span>
                ))}
              </div>
              <div className="results-table-wrap">
                <table className="results-data-table">
                  <thead>
                    <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
                  </thead>
                  <tbody>
                    {(dataset.preview || []).slice(0, 8).map((row, rowIndex) => (
                      <tr key={`row_${rowIndex}`}>
                        {columns.map((column) => <td key={column}>{displayValue(row[column])}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <div className="analytics-empty">
              <strong>No dataset loaded</strong>
              <p>Import submitted form responses or upload a spreadsheet to begin.</p>
            </div>
          )}
        </article>

        <aside className="analytics-side-panel">
          <section className="analytics-card">
            <span className="workspace-kicker">Review</span>
            <h3>Understand the data</h3>
            <div className="analysis-action-row">
              <button type="button" onClick={() => runInspection("overview")} disabled={!dataset || isLoading}>Overview</button>
              <button type="button" onClick={() => runInspection("statistics")} disabled={!dataset || isLoading}>Statistics</button>
              <button type="button" onClick={() => runInspection("missing")} disabled={!dataset || isLoading}>Missing values</button>
              <button type="button" onClick={() => runInspection("quality")} disabled={!dataset || isLoading}>Quality</button>
            </div>
          </section>

          <section className="analytics-card">
            <span className="workspace-kicker">Review result</span>
            <h3>{getFriendlyInspectionTitle(inspection?.type)}</h3>
            <ResultView value={inspection?.data} />
          </section>
        </aside>
      </section>

      <section className="analysis-workflow-grid">
        <article className="analytics-card">
          <span className="workspace-kicker">Prepare</span>
          <h3>Clean the data</h3>
          <p>Select the fixes you want to apply before the analysis runs.</p>

          <div className="analysis-cleaning-grid">
            <label className="analysis-toggle">
              <input type="checkbox" checked={cleaning.trimText} onChange={(event) => updateCleaning("trimText", event.target.checked)} />
              <span>Clean spaces in text columns</span>
            </label>
            <label className="analysis-toggle">
              <input type="checkbox" checked={cleaning.lowercaseText} onChange={(event) => updateCleaning("lowercaseText", event.target.checked)} />
              <span>Standardize text to lowercase</span>
            </label>
            <label className="analysis-toggle">
              <input type="checkbox" checked={cleaning.removeDuplicates} onChange={(event) => updateCleaning("removeDuplicates", event.target.checked)} />
              <span>Remove duplicate rows</span>
            </label>
            <label className="analysis-toggle">
              <input type="checkbox" checked={cleaning.removeMissingRows} onChange={(event) => updateCleaning("removeMissingRows", event.target.checked)} />
              <span>Remove rows with empty answers</span>
            </label>
          </div>

          <div className="analysis-form-grid">
            <label className="analysis-toggle">
              <input type="checkbox" checked={cleaning.fillMissing} onChange={(event) => updateCleaning("fillMissing", event.target.checked)} />
              <span>Fill missing values</span>
            </label>
            <ColumnSelect label="Column to fill" value={cleaning.fillColumn} columns={columns} onChange={(value) => updateCleaning("fillColumn", value)} />
            <label className="analysis-field">
              <span>Fill with</span>
              <select value={cleaning.fillMethod} onChange={(event) => updateCleaning("fillMethod", event.target.value)}>
                <option value="mode">Most common value</option>
                <option value="mean">Average</option>
                <option value="median">Median</option>
                <option value="forward_fill">Previous value</option>
                <option value="backward_fill">Next value</option>
                <option value="constant">Custom value</option>
              </select>
            </label>
            {cleaning.fillMethod === "constant" && (
              <label className="analysis-field">
                <span>Custom value</span>
                <input type="text" value={cleaning.fillValue} onChange={(event) => updateCleaning("fillValue", event.target.value)} />
              </label>
            )}
            <ColumnSelect label="Convert column" value={cleaning.convertColumn} columns={columns} optional onChange={(value) => updateCleaning("convertColumn", value)} />
            <label className="analysis-field">
              <span>Convert to</span>
              <select value={cleaning.convertType} onChange={(event) => updateCleaning("convertType", event.target.value)}>
                <option value="numeric">Number</option>
                <option value="datetime">Date</option>
                <option value="string">Text</option>
                <option value="category">Category</option>
                <option value="boolean">Yes / no</option>
              </select>
            </label>
            <ColumnSelect label="Rename column" value={cleaning.renameColumn} columns={columns} optional onChange={(value) => updateCleaning("renameColumn", value)} />
            <label className="analysis-field">
              <span>New name</span>
              <input type="text" value={cleaning.renameTo} onChange={(event) => updateCleaning("renameTo", event.target.value)} />
            </label>
            <MultiColumnSelect label="Remove outliers from" value={cleaning.outlierColumns} columns={numericColumnGuess} onChange={(value) => {
              updateCleaning("outlierColumns", value);
              updateCleaning("removeOutliers", value.length > 0);
            }} />
            <MultiColumnSelect label="Exclude columns" value={cleaning.dropColumns} columns={columns} onChange={(value) => updateCleaning("dropColumns", value)} />
          </div>
        </article>

        <article className="analytics-card">
          <span className="workspace-kicker">Analyze</span>
          <h3>Choose the report</h3>
          <p>Pick the type of report and map your data columns.</p>

          <div className="analysis-method-tabs">
            {Object.entries(analysisGroups).map(([key, group]) => (
              <button key={key} type="button" className={analysisDomain === key ? "active" : ""} onClick={() => setDomain(key)}>
                <strong>{group.label}</strong>
                <span>{group.description}</span>
              </button>
            ))}
          </div>

          <label className="analysis-field">
            <span>Report</span>
            <select value={analysisMethod} onChange={(event) => setMethod(event.target.value)}>
              {methods.map((method) => <option key={method.id} value={method.id}>{method.label}</option>)}
            </select>
          </label>

          <div className="analysis-form-grid">
            {Object.entries(activeMethod.template).map(renderParamControl)}
          </div>
        </article>
      </section>

      <section className="analytics-card">
        <div className="analytics-card-header">
          <div>
            <span className="workspace-kicker">Result</span>
            <h3>{activeMethod.label}</h3>
            <p>{analysisResult ? "Analysis completed." : "Run the analysis to see the result here."}</p>
          </div>
          <button type="button" className="primary-action" onClick={runAnalysis} disabled={isLoading || !dataset}>
            {isLoading ? "Working..." : "Run analysis"}
          </button>
        </div>
        <ResultView value={analysisPayload} />
      </section>
    </div>
  );
}
