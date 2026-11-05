import DateTimeInput from "../common/DateTimeInput";
import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  Database,
  Download,
  FileText,
  FolderOpen,
  Gauge,
  LayoutDashboard,
  RefreshCw,
  Search,
  Table2,
} from "lucide-react";

import { apiFetch, getApiUrl, readApiResponse } from "../../utils/apiClient";
import "../../styles/admin/business-intelligence.css";

const COPY = {
  en: {
    title: "Business Intelligence",
    subtitle: "Explore an authorized immutable dataset version with deterministic calculations.",
    changeProject: "Change project",
    tabs: ["Overview", "Explore", "Metrics", "Visualizations", "Dashboard", "Reports"],
    dataset: "Dataset",
    version: "Immutable version",
    loading: "Loading business intelligence workspace",
    unavailable: "Business Intelligence is unavailable for this project",
    unavailableHint: "Persistent project datasets require a newer database capability. Data Logs remains available.",
    empty: "No project datasets yet",
    emptyHint: "Connect or upload data in Data Sources, then return here to analyze it.",
    loadError: "The authorized project datasets could not be loaded.",
    select: "Select a dataset",
    versionBound: "Every view and calculation is bound to the selected immutable version.",
    rows: "Rows",
    columns: "Columns",
    missing: "Missing values",
    updated: "Dataset updated",
    source: "Source",
    sourceUnavailable: "Source linkage unavailable in the dataset contract",
    sync: "Last successful synchronization",
    lastEvent: "Last event received",
    lastAttempt: "Last ingestion attempt",
    checkpoint: "Latest analytical checkpoint",
    reconciliation: "Reconciliation",
    pending: "Pending",
    current: "Current",
    syncUnavailable: "Not exposed for this dataset",
    contentHash: "Content hash",
    noHash: "Not available",
    quality: "Technical data quality",
    qualityHint: "Technical profiles do not assign business meaning, units, or currency.",
    preview: "Bounded record preview",
    previewLimit: "The server applies allowlisted filters, stable sorting, and bounded paging to this exact version.",
    filter: "Filter field",
    filterValue: "Filter value",
    filterOperator: "Filter operation",
    sort: "Sort preview by",
    none: "None",
    noRows: "This dataset has no preview rows.",
    column: "Column",
    type: "Technical type",
    filled: "Filled",
    unique: "Distinct",
    metricIntro: "Choose a generic operation. Madar will not infer revenue, profit, currency, units, or accounting meaning.",
    operation: "Operation",
    valueColumn: "Numeric column",
    distinctColumn: "Value column",
    groupColumn: "Group by (optional)",
    run: "Run calculation",
    running: "Calculating…",
    count: "Record count",
    sum: "Sum of selected column",
    mean: "Average of selected column",
    min: "Minimum of selected column",
    max: "Maximum of selected column",
    distinct_count: "Distinct non-missing values",
    date_aggregate: "Date aggregation",
    dateColumn: "Verified date column",
    period: "Period",
    aggregation: "Aggregation",
    customPeriod: "Custom reporting period (optional)",
    startDate: "Start date",
    endDate: "End date",
    reportingTimezone: "Reporting timezone (IANA)",
    periodInvalid: "Choose both dates in chronological order and provide an IANA timezone.",
    dateSemanticsUnavailable: "No technically verified date column is available for this dataset version.",
    periodRows: "Rows inside period",
    missingDates: "Missing dates",
    invalidDates: "Invalid dates",
    outsidePeriod: "Valid rows outside period",
    partialPeriod: "The first or last grouped period is partial for the requested boundaries or observed data coverage.",
    allDates: "All valid dates",
    incompatible: "Choose a numeric column compatible with this operation.",
    result: "Deterministic result",
    noResult: "Run a supported metric to create a result.",
    unknownUnit: "Unit/currency: not declared",
    provenance: "Result provenance",
    chartTitle: "Current result visualization",
    chartHint: "Grouped deterministic results are shown as a bar chart with an accessible data table.",
    chartUnavailable: "A chart becomes available after a grouped or date-based calculation.",
    dashboardTitle: "Persistent dashboards",
    dashboardHint: "Save validated operations with exact dataset-version provenance. Latest-version widgets move only after an explicit successful refresh.",
    persistenceUnavailable: "Persistent dashboards require the unselected schema 163 capability.",
    dashboardName: "Dashboard name",
    dashboardDescription: "Description",
    createDashboard: "Create dashboard",
    saveDashboard: "Save details",
    deleteDashboard: "Delete dashboard",
    addWidget: "Add current result",
    noDashboards: "No dashboards yet.",
    noWidgets: "This dashboard has no widgets.",
    pinned: "Pinned version",
    latest_committed: "Latest committed on explicit refresh",
    refreshWidget: "Refresh to latest",
    removeWidget: "Remove widget",
    widgetWidth: "Widget width",
    widgetHeight: "Widget height",
    widgetTitle: "Widget title",
    widgetType: "Presentation",
    widgetPosition: "Layout position",
    showLegend: "Show chart legend",
    showTable: "Show accessible data table",
    saveWidget: "Save widget",
    chartLegend: "Series",
    chartEmpty: "This verified result has no plottable numeric values.",
    widgetLoading: "Loading verified widget result…",
    sharedWithMe: "Shared with me",
    sharingTitle: "Team sharing",
    sharingHint: "Share only with active members of this workspace. No public link is created.",
    sharingUnavailable: "Team sharing requires the unselected schema 165 capability.",
    member: "Workspace member",
    permission: "Permission",
    viewer: "Viewer",
    editor: "Editor",
    share: "Share",
    revoke: "Revoke",
    noShares: "Not shared with any member.",
    sharedViewer: "Shared viewer",
    sharedEditor: "Shared editor",
    ownerOnly: "Only the owner can manage sharing and destructive actions.",
    reportShareHint: "Immutable reports can be shared for private viewing and download only.",
    deliveryTitle: "Scheduled delivery",
    deliveryHint: "Opt in to private email delivery for active workspace members. No public link is created.",
    deliveryUnavailable: "Report delivery and retention require the unselected schema 166 capability.",
    configureDelivery: "Configure delivery",
    deliveryEnabled: "Deliver completed scheduled reports",
    recipients: "Recipients",
    saveDelivery: "Save delivery",
    retentionTitle: "Private artifact retention",
    retentionDays: "Retention days",
    cleanupEnabled: "Delete private report artifacts after retention",
    saveRetention: "Save retention",
    deliveryHistory: "Delivery history",
    noDeliveries: "No delivery attempts for this report.",
    attempts: "Attempts",
    artifactExpired: "Private export artifact removed under the retention policy.",
    needsAttention: "This widget needs attention because the selected operation is incompatible with the latest dataset schema.",
    reportsTitle: "Recurring reports",
    reportsHint: "Generate immutable, version-bound generic analytical reports with per-widget as-of information.",
    reportingUnavailable: "Automated reporting requires the unselected schema 164 capability.",
    autoRefresh: "Automatically generate a report when a latest-version widget has new committed data",
    autoRefreshHint: "Opt-in only. Pinned widgets never move, and each generated report stores its exact version vector.",
    scheduleName: "Schedule name", cadence: "Cadence", timezone: "Timezone", localTime: "Local time",
    weekday: "Weekday (0 Monday)", monthDay: "Month day", createSchedule: "Create schedule",
    editSchedule: "Edit schedule", saveSchedule: "Save schedule", scheduleEnabled: "Enabled",
    generateNow: "Generate report now", reportHistory: "Report history",
    noReports: "No reports have been generated.", noSchedules: "No recurring schedules.",
    openReport: "Open report", downloadCsv: "Download CSV", downloadPdf: "Download PDF",
    downloadXlsx: "Download XLSX", printReport: "Print report",
    removeSchedule: "Remove schedule", archiveReport: "Archive report", nextRun: "Next run", statusLabel: "Status",
    reportDisclosure: "Generic analytical report — business meaning, units, currencies, and accounting treatment are not inferred.",
    previous: "Previous",
    next: "Next",
    apply: "Apply query",
    semanticTitle: "Semantic metadata status",
    semanticHint: "Business meaning, unit, currency, row grain, relationship validity, confidence, and approval status are not declared. No AI interpretation is active.",
    retry: "Retry",
    missingProfile: "Technical profiling is unavailable for this dataset.",
    stale: "The dataset changed. Previous analysis was cleared.",
  },
  ar: {
    title: "ذكاء الأعمال",
    subtitle: "استكشف إصداراً ثابتاً ومصرحاً من مجموعة البيانات باستخدام حسابات حتمية.",
    changeProject: "تغيير المشروع",
    tabs: ["نظرة عامة", "استكشاف", "المقاييس", "المرئيات", "لوحة المعلومات", "التقارير"],
    dataset: "مجموعة البيانات",
    version: "الإصدار الثابت",
    loading: "جارٍ تحميل مساحة ذكاء الأعمال",
    unavailable: "ذكاء الأعمال غير متاح لهذا المشروع",
    unavailableHint: "تتطلب مجموعات بيانات المشروع الدائمة قدرة أحدث لقاعدة البيانات. تبقى سجلات البيانات متاحة.",
    empty: "لا توجد مجموعات بيانات للمشروع بعد",
    emptyHint: "اربط البيانات أو ارفعها في مصادر البيانات، ثم عد إلى هنا لتحليلها.",
    loadError: "تعذر تحميل مجموعات البيانات المصرح بها للمشروع.",
    select: "اختر مجموعة بيانات",
    versionBound: "ترتبط كل معاينة وحساب بالإصدار الثابت المحدد.",
    rows: "الصفوف",
    columns: "الأعمدة",
    missing: "القيم المفقودة",
    updated: "تحديث مجموعة البيانات",
    source: "المصدر",
    sourceUnavailable: "ارتباط المصدر غير متاح في عقد مجموعة البيانات",
    sync: "آخر مزامنة ناجحة",
    lastEvent: "آخر حدث مستلم",
    lastAttempt: "آخر محاولة إدخال",
    checkpoint: "آخر نقطة تحقق تحليلية",
    reconciliation: "التسوية",
    pending: "قيد الانتظار",
    current: "محدث",
    syncUnavailable: "غير معروض لمجموعة البيانات هذه",
    contentHash: "بصمة المحتوى",
    noHash: "غير متاح",
    quality: "جودة البيانات التقنية",
    qualityHint: "لا تحدد الملفات التقنية المعنى التجاري أو الوحدات أو العملة.",
    preview: "معاينة محدودة للسجلات",
    previewLimit: "يطبق الخادم عوامل التصفية المسموحة والترتيب الثابت والتصفح المحدود على هذا الإصدار.",
    filter: "حقل التصفية",
    filterValue: "قيمة التصفية",
    filterOperator: "عملية التصفية",
    sort: "ترتيب المعاينة حسب",
    none: "بدون",
    noRows: "لا تحتوي مجموعة البيانات على صفوف معاينة.",
    column: "العمود",
    type: "النوع التقني",
    filled: "معبأ",
    unique: "مميز",
    metricIntro: "اختر عملية عامة. لن يفترض مدار الإيرادات أو الربح أو العملة أو الوحدات أو المعنى المحاسبي.",
    operation: "العملية",
    valueColumn: "عمود رقمي",
    distinctColumn: "عمود القيمة",
    groupColumn: "التجميع حسب (اختياري)",
    run: "تنفيذ الحساب",
    running: "جارٍ الحساب…",
    count: "عدد السجلات",
    sum: "مجموع العمود المحدد",
    mean: "متوسط العمود المحدد",
    min: "أدنى قيمة في العمود المحدد",
    max: "أعلى قيمة في العمود المحدد",
    distinct_count: "عدد القيم المميزة غير المفقودة",
    date_aggregate: "تجميع زمني",
    dateColumn: "عمود التاريخ المتحقق منه",
    period: "الفترة",
    aggregation: "التجميع",
    customPeriod: "فترة تقرير مخصصة (اختياري)",
    startDate: "تاريخ البداية",
    endDate: "تاريخ النهاية",
    reportingTimezone: "المنطقة الزمنية للتقرير (IANA)",
    periodInvalid: "اختر تاريخي البداية والنهاية بترتيب صحيح وحدد منطقة زمنية من IANA.",
    dateSemanticsUnavailable: "لا يتوفر عمود تاريخ متحقق منه تقنياً في إصدار مجموعة البيانات هذا.",
    periodRows: "الصفوف داخل الفترة",
    missingDates: "التواريخ المفقودة",
    invalidDates: "التواريخ غير الصالحة",
    outsidePeriod: "الصفوف المؤرخة خارج الفترة",
    partialPeriod: "الفترة المجمعة الأولى أو الأخيرة جزئية بسبب الحدود المطلوبة أو تغطية البيانات المرصودة.",
    allDates: "جميع التواريخ الصالحة",
    incompatible: "اختر عموداً رقمياً متوافقاً مع هذه العملية.",
    result: "نتيجة حتمية",
    noResult: "نفذ مقياساً مدعوماً لإنشاء نتيجة.",
    unknownUnit: "الوحدة/العملة: غير معلنة",
    provenance: "مصدر النتيجة",
    chartTitle: "مرئية النتيجة الحالية",
    chartHint: "تظهر النتائج المجمعة كمخطط أعمدة مع جدول بيانات بديل قابل للوصول.",
    chartUnavailable: "يصبح المخطط متاحاً بعد حساب مجمع أو زمني.",
    dashboardTitle: "لوحات معلومات دائمة",
    dashboardHint: "احفظ العمليات المتحققة مع مصدر إصدار البيانات الدقيق. لا تنتقل أدوات أحدث إصدار إلا بعد تحديث صريح وناجح.",
    persistenceUnavailable: "تتطلب لوحات المعلومات الدائمة قدرة المخطط 163 غير المحددة للإصدار النشط.",
    dashboardName: "اسم لوحة المعلومات",
    dashboardDescription: "الوصف",
    createDashboard: "إنشاء لوحة معلومات",
    saveDashboard: "حفظ التفاصيل",
    deleteDashboard: "حذف لوحة المعلومات",
    addWidget: "إضافة النتيجة الحالية",
    noDashboards: "لا توجد لوحات معلومات بعد.",
    noWidgets: "لا تحتوي لوحة المعلومات على أدوات.",
    pinned: "إصدار مثبت",
    latest_committed: "أحدث إصدار عند التحديث الصريح",
    refreshWidget: "تحديث إلى الأحدث",
    removeWidget: "إزالة الأداة",
    widgetWidth: "عرض الأداة",
    widgetHeight: "ارتفاع الأداة",
    widgetTitle: "عنوان الأداة",
    widgetType: "طريقة العرض",
    widgetPosition: "موضع التخطيط",
    showLegend: "إظهار مفتاح الرسم",
    showTable: "إظهار جدول البيانات المتاح",
    saveWidget: "حفظ الأداة",
    chartLegend: "السلسلة",
    chartEmpty: "لا تحتوي هذه النتيجة المتحققة على قيم رقمية قابلة للرسم.",
    widgetLoading: "جارٍ تحميل نتيجة الأداة المتحققة…",
    sharedWithMe: "تمت مشاركتها معي",
    sharingTitle: "المشاركة مع الفريق",
    sharingHint: "شارك فقط مع أعضاء مساحة العمل النشطين. لا يتم إنشاء رابط عام.",
    sharingUnavailable: "تتطلب مشاركة الفريق قدرة المخطط 165 غير المحددة للإصدار النشط.",
    member: "عضو مساحة العمل",
    permission: "الصلاحية",
    viewer: "مشاهد",
    editor: "محرر",
    share: "مشاركة",
    revoke: "إلغاء الوصول",
    noShares: "لم تتم المشاركة مع أي عضو.",
    sharedViewer: "مشاهد مشارك",
    sharedEditor: "محرر مشارك",
    ownerOnly: "يمكن للمالك فقط إدارة المشاركة والإجراءات المتلفة.",
    reportShareHint: "يمكن مشاركة التقارير الثابتة للعرض والتنزيل الخاص فقط.",
    deliveryTitle: "تسليم التقارير المجدولة",
    deliveryHint: "فعّل تسليم البريد الخاص لأعضاء مساحة العمل النشطين. لا يتم إنشاء رابط عام.",
    deliveryUnavailable: "يتطلب تسليم التقارير والاحتفاظ بها قدرة المخطط 166 غير المحددة للإصدار النشط.",
    configureDelivery: "إعداد التسليم",
    deliveryEnabled: "تسليم التقارير المجدولة المكتملة",
    recipients: "المستلمون",
    saveDelivery: "حفظ التسليم",
    retentionTitle: "الاحتفاظ بملفات التقارير الخاصة",
    retentionDays: "أيام الاحتفاظ",
    cleanupEnabled: "حذف ملفات التقارير الخاصة بعد مدة الاحتفاظ",
    saveRetention: "حفظ الاحتفاظ",
    deliveryHistory: "سجل التسليم",
    noDeliveries: "لا توجد محاولات تسليم لهذا التقرير.",
    attempts: "المحاولات",
    artifactExpired: "تم حذف ملف التصدير الخاص وفق سياسة الاحتفاظ.",
    needsAttention: "تحتاج هذه الأداة إلى مراجعة لأن العملية المحددة غير متوافقة مع مخطط أحدث إصدار.",
    reportsTitle: "التقارير الدورية",
    reportsHint: "أنشئ تقارير تحليلية عامة ثابتة مرتبطة بإصدار البيانات الدقيق لكل أداة.",
    reportingUnavailable: "تتطلب التقارير الآلية قدرة المخطط 164 غير المحددة للإصدار النشط.",
    autoRefresh: "إنشاء تقرير تلقائياً عند توفر بيانات ملتزمة جديدة لأداة تستخدم أحدث إصدار",
    autoRefreshHint: "هذه الميزة اختيارية. لا تتغير الأدوات المثبتة، ويحفظ كل تقرير متجه الإصدارات الدقيق.",
    scheduleName: "اسم الجدول", cadence: "التكرار", timezone: "المنطقة الزمنية", localTime: "الوقت المحلي",
    weekday: "يوم الأسبوع (0 الاثنين)", monthDay: "يوم الشهر", createSchedule: "إنشاء جدول",
    editSchedule: "تعديل الجدول", saveSchedule: "حفظ الجدول", scheduleEnabled: "مفعّل",
    generateNow: "إنشاء تقرير الآن", reportHistory: "سجل التقارير",
    noReports: "لم يتم إنشاء تقارير بعد.", noSchedules: "لا توجد جداول دورية.",
    openReport: "فتح التقرير", downloadCsv: "تنزيل CSV", downloadPdf: "تنزيل PDF",
    downloadXlsx: "تنزيل XLSX", printReport: "طباعة التقرير",
    removeSchedule: "إزالة الجدول", archiveReport: "أرشفة التقرير", nextRun: "التشغيل التالي", statusLabel: "الحالة",
    reportDisclosure: "تقرير تحليلي عام — لا يتم استنتاج المعنى التجاري أو الوحدات أو العملات أو المعالجة المحاسبية.",
    previous: "السابق",
    next: "التالي",
    apply: "تطبيق الاستعلام",
    semanticTitle: "حالة البيانات الوصفية الدلالية",
    semanticHint: "المعنى التجاري والوحدة والعملة وحبيبة الصف وصحة العلاقات والثقة وحالة الاعتماد غير معلنة. لا يوجد تفسير بالذكاء الاصطناعي.",
    retry: "إعادة المحاولة",
    missingProfile: "التوصيف التقني غير متاح لمجموعة البيانات هذه.",
    stale: "تغيرت مجموعة البيانات. تم مسح التحليل السابق.",
  },
};

const OPERATIONS = ["count", "sum", "mean", "min", "max", "distinct_count", "date_aggregate"];
const formatDate = (value, lang) => {
  const date = new Date(value || "");
  return Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat(lang === "ar" ? "ar" : "en", { dateStyle: "medium", timeStyle: "short" }).format(date)
    : "—";
};
const formatNumber = (value, lang) => (
  typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat(lang === "ar" ? "ar" : "en", { maximumFractionDigits: 4 }).format(value)
    : String(value ?? "—")
);
const detailMessage = (body, fallback) => {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail.message === "string") return detail.message;
  return fallback;
};
const profileType = (column, types, statistics) => {
  const direct = types?.[column] ?? types?.column_types?.[column];
  if (direct && typeof direct === "object") return direct.type || direct.dtype || "text";
  if (direct) return String(direct);
  if (statistics?.numeric_columns?.[column]) return "number";
  if (statistics?.categorical_columns?.[column]) return "category";
  return "text";
};
const profileFor = (column, statistics, missing) => {
  const stats = statistics?.numeric_columns?.[column] || statistics?.categorical_columns?.[column] || {};
  const gaps = missing?.[column] || {};
  return {
    count: stats.filled_values ?? stats.count ?? null,
    unique: stats.unique_count ?? stats.count ?? null,
    missing: gaps.missing_count ?? stats.missing_values ?? 0,
    missingPercentage: gaps.missing_percentage ?? stats.missing_percentage ?? 0,
  };
};

function StatePanel({ icon: Icon = Database, title, children, action, role = "status" }) {
  return (
    <section className="bi-state" role={role}>
      <Icon size={28} aria-hidden="true" />
      <div><h2>{title}</h2><p>{children}</p>{action}</div>
    </section>
  );
}

function ResultTable({ rows = [], caption = "" }) {
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row || {})))];
  if (!rows.length || !columns.length) return null;
  return (
    <div className="bi-table-scroll">
      <table className="bi-table">
        {caption ? <caption className="bi-table-caption">{caption}</caption> : null}
        <thead><tr>{columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => (
          <tr key={index}>{columns.map((column) => <td key={column} dir="auto">{String(row?.[column] ?? "—")}</td>)}</tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function PeriodDisclosure({ report, copy }) {
  const period = report?.metadata?.mappings_used;
  if (!period?.date_column) return null;
  const selectedRange = period.requested_start_date && period.requested_end_date
    ? `${period.requested_start_date} — ${period.requested_end_date}` : copy.allDates;
  return <aside className="bi-period-disclosure" role="status">
    <strong>{copy.customPeriod}</strong>
    <dl>
      <div><dt>{copy.period}</dt><dd dir="ltr">{selectedRange}</dd></div>
      <div><dt>{copy.reportingTimezone}</dt><dd dir="ltr">{period.timezone || "UTC"}</dd></div>
      <div><dt>{copy.periodRows}</dt><dd>{period.selected_row_count ?? "—"}</dd></div>
      <div><dt>{copy.missingDates}</dt><dd>{period.missing_date_count ?? 0}</dd></div>
      <div><dt>{copy.invalidDates}</dt><dd>{period.invalid_date_count ?? 0}</dd></div>
      <div><dt>{copy.outsidePeriod}</dt><dd>{period.outside_period_count ?? 0}</dd></div>
    </dl>
    {period.partial_periods ? <p className="bi-warning">{copy.partialPeriod}</p> : null}
  </aside>;
}

function AccessibleChart({ chart, lang, showLegend = true, showTable = true, emptyLabel = "", legendLabel = "Series" }) {
  const titleId = useId();
  const rows = Array.isArray(chart?.data) ? chart.data.slice(0, 30) : [];
  const xKey = chart?.x;
  const yKey = chart?.y;
  const plottedRows = rows.filter((row) => Number.isFinite(Number(row?.[yKey])));
  const numericValues = plottedRows.map((row) => Number(row?.[yKey]));
  const maximum = Math.max(0, ...numericValues.map((value) => Math.abs(value)));
  if (!rows.length || !xKey || !yKey || !maximum) return <p className="bi-empty-inline">{emptyLabel}</p>;
  const isLine = chart?.type === "line";
  const points = plottedRows.map((row, index) => {
    const x = plottedRows.length === 1 ? 50 : 4 + (index / (plottedRows.length - 1)) * 92;
    const y = 94 - (Math.abs(Number(row[yKey])) / maximum) * 88;
    return { x, y, row };
  });
  return (
    <figure className="bi-chart" aria-labelledby={titleId}>
      <figcaption id={titleId}>{chart.title}</figcaption>
      {showLegend ? <div className="bi-chart-legend" aria-label={`${legendLabel}: ${yKey}`}><i aria-hidden="true" /><span>{legendLabel}: {yKey}</span></div> : null}
      {isLine ? <div className="bi-line-chart" role="img" aria-label={chart.title}>
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <polyline points={points.map((point) => `${point.x},${point.y}`).join(" ")} />
          {points.map((point, index) => <circle key={index} cx={point.x} cy={point.y} r="1.7" />)}
        </svg>
        <ol>{points.map((point, index) => <li key={`${String(point.row?.[xKey])}-${index}`}><span dir="auto">{String(point.row?.[xKey] ?? "—")}</span><strong>{formatNumber(point.row?.[yKey], lang)}</strong></li>)}</ol>
      </div> : <div className="bi-bars" role="img" aria-label={chart.title}>
        {plottedRows.map((row, index) => {
          const value = Number(row?.[yKey]);
          const width = Number.isFinite(value) ? Math.max(2, Math.abs(value) / maximum * 100) : 0;
          return (
            <div className="bi-bar-row" key={`${String(row?.[xKey])}-${index}`}>
              <span dir="auto" title={String(row?.[xKey] ?? "—")}>{String(row?.[xKey] ?? "—")}</span>
              <i><b style={{ inlineSize: `${width}%` }} /></i>
              <strong>{formatNumber(value, lang)}</strong>
            </div>
          );
        })}
      </div>}
      {showTable ? <ResultTable rows={rows} caption={chart.title} /> : null}
    </figure>
  );
}

function SharingPanel({ copy, members, shares, selectedMemberId, permission, viewerOnly = false,
  onMemberChange, onPermissionChange, onShare, onRevoke }) {
  const availableMembers = members.filter((member) => !shares.some((share) => Number(share.member_user_id) === Number(member.id)));
  return <section className="bi-sharing" aria-labelledby="bi-sharing-title">
    <header><div><h3 id="bi-sharing-title">{copy.sharingTitle}</h3><p>{viewerOnly ? copy.reportShareHint : copy.sharingHint}</p></div></header>
    <div className="bi-sharing-controls">
      <label>{copy.member}<select aria-label={copy.member} value={selectedMemberId} onChange={(event) => onMemberChange(event.target.value)}><option value="">{copy.member}</option>{availableMembers.map((member) => <option key={member.id} value={member.id}>{`${member.first_name || ""} ${member.last_name || ""}`.trim() || member.email} · {member.email}</option>)}</select></label>
      {!viewerOnly ? <label>{copy.permission}<select aria-label={copy.permission} value={permission} onChange={(event) => onPermissionChange(event.target.value)}><option value="viewer">{copy.viewer}</option><option value="editor">{copy.editor}</option></select></label> : null}
      <button type="button" disabled={!selectedMemberId} onClick={onShare}>{copy.share}</button>
    </div>
    {shares.length ? <ul className="bi-sharing-list">{shares.map((share) => <li key={share.id}><div><strong>{`${share.member?.first_name || ""} ${share.member?.last_name || ""}`.trim() || share.member?.email || share.member_user_id}</strong><small>{share.member?.email || ""} · {share.permission === "editor" ? copy.editor : copy.viewer}</small></div><button type="button" onClick={() => onRevoke(share)}>{copy.revoke}</button></li>)}</ul> : <p className="bi-empty-inline">{copy.noShares}</p>}
  </section>;
}

function DashboardWidget({ widget, execution, lang, copy, canEdit = true, onSave, onRefresh, onRemove }) {
  const widgetReport = execution?.result;
  const chart = widgetReport?.charts?.[0] || null;
  const [draft, setDraft] = useState(() => ({
    title: widget.title,
    widget_type: widget.widget_type,
    layout_config: { x: 0, y: 0, w: 6, h: 4, ...(widget.layout_config || {}) },
    display_options: { show_table: true, show_legend: true, ...(widget.display_options || {}) },
  }));
  const supportedTypes = [
    ...(widgetReport?.kpis?.length ? ["kpi"] : []),
    ...(widgetReport?.tables?.[0]?.rows?.length ? ["table"] : []),
    ...(chart ? ["bar", "line"] : []),
  ];
  if (!supportedTypes.includes(widget.widget_type)) supportedTypes.unshift(widget.widget_type);
  const layout = draft.layout_config;
  const setLayout = (key, value) => setDraft((current) => ({ ...current,
    layout_config: { ...current.layout_config, [key]: Number(value) },
  }));
  const renderedChart = chart ? { ...chart, type: draft.widget_type === "line" ? "line" : "bar" } : null;
  const showChart = ["bar", "line"].includes(draft.widget_type) && renderedChart;
  const style = {
    "--bi-widget-columns": Math.min(12, Math.max(1, layout.w)),
    "--bi-widget-rows": Math.min(12, Math.max(1, layout.h)),
    order: Math.min(1000, Math.max(0, layout.y)) * 12 + Math.min(11, Math.max(0, layout.x)),
  };
  return <article className="bi-widget" style={style}>
    <header><div><h3>{widget.title}</h3><small>{widget.version_policy === "pinned" ? copy.pinned : copy.latest_committed} · v{execution?.provenance?.version_number || "—"}</small></div>{canEdit ? <div><button type="button" onClick={onRefresh}>{copy.refreshWidget}</button><button type="button" onClick={onRemove}>{copy.removeWidget}</button></div> : null}</header>
    {canEdit ? <details className="bi-widget-editor"><summary>{copy.saveWidget}</summary><div>
      <label>{copy.widgetTitle}<input value={draft.title} maxLength="160" onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))} /></label>
      <label>{copy.widgetType}<select value={draft.widget_type} onChange={(event) => setDraft((current) => ({ ...current, widget_type: event.target.value }))}>{supportedTypes.map((type) => <option key={type} value={type}>{type}</option>)}</select></label>
      <label>{copy.widgetWidth}<select value={layout.w} onChange={(event) => { const width = Number(event.target.value); setDraft((current) => ({ ...current, layout_config: { ...current.layout_config, w: width, x: Math.min(current.layout_config.x, 12 - width) } })); }}>{[3, 4, 6, 8, 12].map((value) => <option key={value} value={value}>{value}/12</option>)}</select></label>
      <label>{copy.widgetHeight}<select value={layout.h} onChange={(event) => setLayout("h", event.target.value)}>{[3, 4, 6, 8, 12].map((value) => <option key={value}>{value}</option>)}</select></label>
      <label>{copy.widgetPosition} X<input type="number" min="0" max={12 - layout.w} value={layout.x} onChange={(event) => setLayout("x", Math.min(12 - layout.w, Math.max(0, Number(event.target.value))))} /></label>
      <label>{copy.widgetPosition} Y<input type="number" min="0" max="1000" value={layout.y} onChange={(event) => setLayout("y", Math.min(1000, Math.max(0, Number(event.target.value))))} /></label>
      <label className="bi-widget-check"><input type="checkbox" checked={draft.display_options.show_legend} onChange={(event) => setDraft((current) => ({ ...current, display_options: { ...current.display_options, show_legend: event.target.checked } }))} />{copy.showLegend}</label>
      <label className="bi-widget-check"><input type="checkbox" checked={draft.display_options.show_table} onChange={(event) => setDraft((current) => ({ ...current, display_options: { ...current.display_options, show_table: event.target.checked } }))} />{copy.showTable}</label>
      <button type="button" disabled={!draft.title.trim()} onClick={() => onSave(draft)}>{copy.saveWidget}</button>
    </div></details> : null}
    {execution === undefined ? <p className="bi-empty-inline" role="status">{copy.widgetLoading}</p> : execution?.status === "needs_attention" ? <p className="bi-warning">{execution.message || copy.needsAttention}</p> : <>
      {draft.widget_type === "kpi" && widgetReport?.kpis?.[0] ? <strong className="bi-widget-kpi">{widgetReport.kpis[0].display_value ?? formatNumber(widgetReport.kpis[0].value, lang)}</strong> : null}
      {showChart ? <AccessibleChart chart={renderedChart} lang={lang} showLegend={draft.display_options.show_legend} showTable={draft.display_options.show_table} emptyLabel={copy.chartEmpty} legendLabel={copy.chartLegend} /> : null}
      {draft.widget_type === "table" ? <ResultTable rows={widgetReport?.tables?.[0]?.rows || []} caption={widget.title} /> : null}
      <PeriodDisclosure report={widgetReport} copy={copy} />
    </>}
    <details><summary>{copy.provenance}</summary><code>{execution?.provenance?.dataset_version_id || widget.dataset_version_id}</code></details>
  </article>;
}

export default function BusinessIntelligenceWorkspace({ lang = "en", projectId, user, onChangeProject }) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const t = COPY[activeLang];
  const [tab, setTab] = useState("Overview");
  const [datasets, setDatasets] = useState([]);
  const [available, setAvailable] = useState(true);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  const [selectedDatasetId, setSelectedDatasetId] = useState("");
  const [versions, setVersions] = useState([]);
  const [selectedVersionId, setSelectedVersionId] = useState("");
  const [dataset, setDataset] = useState(null);
  const [freshness, setFreshness] = useState(null);
  const [profiles, setProfiles] = useState({ statistics: null, missing: null, types: null });
  const [profileStatus, setProfileStatus] = useState("idle");
  const [filterColumn, setFilterColumn] = useState("");
  const [filterOperator, setFilterOperator] = useState("eq");
  const [filterValue, setFilterValue] = useState("");
  const [sortColumn, setSortColumn] = useState("");
  const [sortDirection, setSortDirection] = useState("asc");
  const [exploration, setExploration] = useState(null);
  const [exploreStatus, setExploreStatus] = useState("idle");
  const [exploreError, setExploreError] = useState("");
  const [operation, setOperation] = useState("count");
  const [valueColumn, setValueColumn] = useState("");
  const [groupColumn, setGroupColumn] = useState("");
  const [dateColumn, setDateColumn] = useState("");
  const [period, setPeriod] = useState("month");
  const [aggregation, setAggregation] = useState("count");
  const [periodStartDate, setPeriodStartDate] = useState("");
  const [periodEndDate, setPeriodEndDate] = useState("");
  const [reportingTimezone, setReportingTimezone] = useState("UTC");
  const [metricStatus, setMetricStatus] = useState("idle");
  const [metricError, setMetricError] = useState("");
  const [metricResult, setMetricResult] = useState(null);
  const [dashboardsAvailable, setDashboardsAvailable] = useState(true);
  const [dashboards, setDashboards] = useState([]);
  const [selectedDashboardId, setSelectedDashboardId] = useState("");
  const [dashboard, setDashboard] = useState(null);
  const [dashboardName, setDashboardName] = useState("");
  const [dashboardDescription, setDashboardDescription] = useState("");
  const [dashboardError, setDashboardError] = useState("");
  const [versionPolicy, setVersionPolicy] = useState("pinned");
  const [widgetWidth, setWidgetWidth] = useState(6);
  const [widgetHeight, setWidgetHeight] = useState(4);
  const [widgetResults, setWidgetResults] = useState({});
  const [sharingAvailable, setSharingAvailable] = useState(true);
  const [dashboardShares, setDashboardShares] = useState([]);
  const [dashboardMembers, setDashboardMembers] = useState([]);
  const [dashboardShareMember, setDashboardShareMember] = useState("");
  const [dashboardSharePermission, setDashboardSharePermission] = useState("viewer");
  const [reportShares, setReportShares] = useState([]);
  const [reportMembers, setReportMembers] = useState([]);
  const [reportShareMember, setReportShareMember] = useState("");
  const [deliveryAvailable, setDeliveryAvailable] = useState(true);
  const [deliverySchedule, setDeliverySchedule] = useState(null);
  const [deliveryEnabled, setDeliveryEnabled] = useState(false);
  const [deliveryMembers, setDeliveryMembers] = useState([]);
  const [deliveryRecipients, setDeliveryRecipients] = useState([]);
  const [deliveryHistory, setDeliveryHistory] = useState([]);
  const [lifecycleSettings, setLifecycleSettings] = useState({ retention_days: 90, cleanup_enabled: false, revision: 0 });
  const [reportingAvailable, setReportingAvailable] = useState(true);
  const [schedules, setSchedules] = useState([]);
  const [reports, setReports] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [reportError, setReportError] = useState("");
  const [scheduleName, setScheduleName] = useState("");
  const [scheduleCadence, setScheduleCadence] = useState("weekly");
  const [scheduleTimezone, setScheduleTimezone] = useState("UTC");
  const [scheduleTime, setScheduleTime] = useState("09:00");
  const [scheduleWeekday, setScheduleWeekday] = useState(0);
  const [scheduleMonthDay, setScheduleMonthDay] = useState(1);
  const [scheduleEnabled, setScheduleEnabled] = useState(true);
  const [editingScheduleId, setEditingScheduleId] = useState("");
  const selectionRequestRef = useRef(0);
  const metricRequestRef = useRef(0);

  const userRoot = user?.id ? getApiUrl(`/users/${encodeURIComponent(user.id)}`) : "";
  const projectRoot = userRoot && projectId
    ? `${userRoot}/data/projects/${encodeURIComponent(projectId)}`
    : "";

  const loadDatasets = useCallback(async () => {
    if (!projectRoot) {
      setStatus("error");
      setError(t.loadError);
      return;
    }
    setStatus("loading");
    setError("");
    try {
      const response = await apiFetch(`${projectRoot}/datasets?limit=100`, { credentials: "include" });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      const items = Array.isArray(body.items) ? body.items : [];
      setAvailable(body.available !== false);
      setDatasets(items);
      setSelectedDatasetId((current) => items.some((item) => item.id === current) ? current : (items[0]?.id || ""));
      setStatus("ready");
    } catch (requestError) {
      setStatus("error");
      setError(requestError.message || t.loadError);
    }
  }, [projectRoot, t.loadError]);

  const loadDashboards = useCallback(async () => {
    if (!projectRoot) return;
    try {
      const [response, sharedResponse] = await Promise.all([
        apiFetch(`${projectRoot}/dashboards?limit=100`, { credentials: "include" }),
        apiFetch(`${projectRoot}/shared-dashboards`, { credentials: "include" }),
      ]);
      const [body, sharedBody] = await Promise.all([readApiResponse(response), readApiResponse(sharedResponse)]);
      if (!response.ok || !sharedResponse.ok) throw new Error(detailMessage(body, detailMessage(sharedBody, t.loadError)));
      const owned = (Array.isArray(body.items) ? body.items : []).map((item) => ({ ...item,
        access: item.access || { is_owner: true, permission: "owner", can_edit: true, can_share: true },
      }));
      const shared = Array.isArray(sharedBody.items) ? sharedBody.items : [];
      const items = [...owned, ...shared.filter((item) => !owned.some((ownedItem) => ownedItem.id === item.id))];
      setDashboardsAvailable(body.available !== false);
      setSharingAvailable(sharedBody.available !== false);
      setDashboards(items);
      setSelectedDashboardId((current) => items.some((item) => item.id === current) ? current : (items[0]?.id || ""));
    } catch (requestError) {
      setDashboardError(requestError.message || t.loadError);
    }
  }, [projectRoot, t.loadError]);

  const loadReports = useCallback(async () => {
    if (!projectRoot) return;
    try {
      const [scheduleResponse, reportResponse, sharedResponse, lifecycleResponse] = await Promise.all([
        apiFetch(`${projectRoot}/report-schedules`, { credentials: "include" }),
        apiFetch(`${projectRoot}/reports?limit=50`, { credentials: "include" }),
        apiFetch(`${projectRoot}/shared-reports`, { credentials: "include" }),
        apiFetch(`${projectRoot}/report-lifecycle`, { credentials: "include" }),
      ]);
      const scheduleBody = await readApiResponse(scheduleResponse);
      const reportBody = await readApiResponse(reportResponse);
      const sharedBody = await readApiResponse(sharedResponse);
      const lifecycleBody = await readApiResponse(lifecycleResponse);
      if (!scheduleResponse.ok || !reportResponse.ok || !sharedResponse.ok || !lifecycleResponse.ok) throw new Error(detailMessage(scheduleBody, detailMessage(reportBody, detailMessage(sharedBody, detailMessage(lifecycleBody, t.loadError)))));
      const isAvailable = scheduleBody.available !== false && reportBody.available !== false;
      setReportingAvailable(isAvailable);
      setSchedules(Array.isArray(scheduleBody.items) ? scheduleBody.items : []);
      setSharingAvailable(sharedBody.available !== false);
      setDeliveryAvailable(lifecycleBody.available !== false);
      if (lifecycleBody.settings) setLifecycleSettings(lifecycleBody.settings);
      const owned = (Array.isArray(reportBody.items) ? reportBody.items : []).map((item) => ({ ...item,
        access: item.access || { is_owner: true, permission: "owner", can_edit: true, can_share: true },
      }));
      const shared = Array.isArray(sharedBody.items) ? sharedBody.items : [];
      setReports([...owned, ...shared.filter((item) => !owned.some((ownedItem) => ownedItem.id === item.id))]);
    } catch (requestError) { setReportError(requestError.message || t.loadError); }
  }, [projectRoot, t.loadError]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => { void loadDatasets(); void loadDashboards(); void loadReports(); }, 0);
    return () => window.clearTimeout(timeoutId);
  }, [loadDashboards, loadDatasets, loadReports]);

  useEffect(() => {
    const requestId = selectionRequestRef.current + 1;
    selectionRequestRef.current = requestId;
    metricRequestRef.current += 1;
    if (!selectedDatasetId || !projectRoot) {
      return undefined;
    }
    const controller = new AbortController();
    void (async () => {
      setProfileStatus("loading");
      setDataset(null);
      setVersions([]);
      setSelectedVersionId("");
      setFreshness(null);
      try {
        const [versionsResponse, freshnessResponse] = await Promise.all([
          apiFetch(`${projectRoot}/datasets/${encodeURIComponent(selectedDatasetId)}/versions?limit=100`, { credentials: "include", signal: controller.signal }),
          apiFetch(`${projectRoot}/datasets/${encodeURIComponent(selectedDatasetId)}/freshness`, { credentials: "include", signal: controller.signal }),
        ]);
        const [versionsBody, freshnessBody] = await Promise.all([readApiResponse(versionsResponse), readApiResponse(freshnessResponse)]);
        if (!versionsResponse.ok) throw new Error(detailMessage(versionsBody, t.loadError));
        if (selectionRequestRef.current !== requestId) return;
        const items = Array.isArray(versionsBody.items) ? versionsBody.items : [];
        setVersions(items);
        setSelectedVersionId(items[0]?.id || "");
        setFreshness(freshnessResponse.ok ? freshnessBody : null);
      } catch (requestError) {
        if (controller.signal.aborted || selectionRequestRef.current !== requestId) return;
        setError(requestError.message || t.loadError);
        setProfileStatus("error");
      }
    })();
    return () => controller.abort();
  }, [projectRoot, selectedDatasetId, t.loadError]);

  useEffect(() => {
    if (!selectedDatasetId || !selectedVersionId || !projectRoot) return undefined;
    const requestId = selectionRequestRef.current + 1;
    selectionRequestRef.current = requestId;
    metricRequestRef.current += 1;
    const controller = new AbortController();
    void (async () => {
      setProfileStatus("loading");
      setDataset(null);
      setExploration(null);
      setExploreStatus("loading");
      try {
        const exactRoot = `${projectRoot}/datasets/${encodeURIComponent(selectedDatasetId)}/versions/${encodeURIComponent(selectedVersionId)}`;
        const [response, exploreResponse] = await Promise.all([
          apiFetch(exactRoot, { credentials: "include", signal: controller.signal }),
          apiFetch(`${exactRoot}/explore`, {
            method: "POST", credentials: "include", signal: controller.signal,
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ columns: [], filters: [], sort: [], limit: 50, offset: 0 }),
          }),
        ]);
        const [body, exploreBody] = await Promise.all([readApiResponse(response), readApiResponse(exploreResponse)]);
        if (!response.ok) throw new Error(detailMessage(body, t.loadError));
        if (!exploreResponse.ok) throw new Error(detailMessage(exploreBody, t.loadError));
        if (selectionRequestRef.current !== requestId) return;
        setDataset(body);
        setExploration(exploreBody);
        setExploreStatus("ready");
        const profilePaths = ["statistics", "missing-report", "column-types"];
        const responses = await Promise.all(profilePaths.map((path) => apiFetch(`${userRoot}/cleaning/${path}`, {
          method: "POST", credentials: "include", signal: controller.signal,
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ input_path: body.file_path }),
        })));
        const payloads = await Promise.all(responses.map(readApiResponse));
        if (selectionRequestRef.current !== requestId) return;
        setProfiles({
          statistics: responses[0].ok ? payloads[0] : null,
          missing: responses[1].ok ? payloads[1] : null,
          types: responses[2].ok ? payloads[2] : null,
        });
        setProfileStatus(responses.some((item) => !item.ok) ? "partial" : "ready");
      } catch (requestError) {
        if (controller.signal.aborted || selectionRequestRef.current !== requestId) return;
        setError(requestError.message || t.loadError);
        setExploreError(requestError.message || t.loadError);
        setExploreStatus("error");
        setProfileStatus("error");
      }
    })();
    return () => controller.abort();
  }, [projectRoot, selectedDatasetId, selectedVersionId, t.loadError, userRoot]);

  useEffect(() => {
    if (!selectedDashboardId || !projectRoot || !dashboardsAvailable) {
      return undefined;
    }
    let active = true;
    void (async () => {
      try {
        const response = await apiFetch(`${projectRoot}/dashboards/${encodeURIComponent(selectedDashboardId)}`, { credentials: "include" });
        const body = await readApiResponse(response);
        if (!response.ok) throw new Error(detailMessage(body, t.loadError));
        if (!active) return;
        const normalized = { ...body, access: body.access || { is_owner: true, permission: "owner", can_edit: true, can_share: true } };
        setDashboard(normalized);
        setDashboardName(body.name || "");
        setDashboardDescription(body.description || "");
        setDashboardShares([]);
        setDashboardMembers([]);
        setDashboardShareMember("");
        if (normalized.access.is_owner && sharingAvailable) {
          const sharesResponse = await apiFetch(`${projectRoot}/dashboards/${encodeURIComponent(body.id)}/shares`, { credentials: "include" });
          const sharesBody = await readApiResponse(sharesResponse);
          if (!sharesResponse.ok) throw new Error(detailMessage(sharesBody, t.loadError));
          if (!active) return;
          setDashboardShares(Array.isArray(sharesBody.items) ? sharesBody.items : []);
          setDashboardMembers(Array.isArray(sharesBody.members) ? sharesBody.members : []);
        }
        const executions = await Promise.all((body.widgets || []).map(async (widget) => {
          const execute = await apiFetch(`${projectRoot}/dashboards/${encodeURIComponent(body.id)}/widgets/${encodeURIComponent(widget.id)}/execute`, {
            method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_latest: false, language: activeLang }),
          });
          return [widget.id, execute.ok ? await readApiResponse(execute) : null];
        }));
        if (active) setWidgetResults(Object.fromEntries(executions));
      } catch (requestError) {
        if (active) setDashboardError(requestError.message || t.loadError);
      }
    })();
    return () => { active = false; };
  }, [activeLang, dashboardsAvailable, projectRoot, selectedDashboardId, sharingAvailable, t.loadError]);

  const selectedRegistryDataset = datasets.find((item) => item.id === selectedDatasetId) || null;
  const version = versions.find((item) => item.id === selectedVersionId) || null;
  const columns = useMemo(() => Array.isArray(dataset?.columns) ? dataset.columns : [], [dataset]);
  const previewRows = useMemo(() => Array.isArray(exploration?.rows) ? exploration.rows : [], [exploration]);
  const numericColumns = useMemo(() => columns.filter((column) => (
    Object.prototype.hasOwnProperty.call(profiles.statistics?.numeric_columns || {}, column) ||
    /^(number|numeric|integer|int|float|float64|money|decimal)/.test(profileType(column, profiles.types, profiles.statistics).toLowerCase())
  )), [columns, profiles.statistics, profiles.types]);
  const dateColumns = useMemo(() => columns.filter((column) => (
    /date|time/.test(profileType(column, profiles.types, profiles.statistics).toLowerCase()) ||
    exploration?.columns?.some((item) => item.name === column && item.technical_type === "datetime")
  )), [columns, exploration?.columns, profiles.statistics, profiles.types]);
  const operationNeedsNumeric = ["sum", "mean", "min", "max"].includes(operation) || (operation === "date_aggregate" && aggregation !== "count");
  const operationNeedsValue = operationNeedsNumeric || operation === "distinct_count";
  const effectiveValueColumn = operationNeedsValue && !(operation === "distinct_count" ? columns : numericColumns).includes(valueColumn)
    ? ((operation === "distinct_count" ? columns[0] : numericColumns[0]) || "")
    : valueColumn;
  const customPeriodRequested = Boolean(periodStartDate || periodEndDate);
  const periodSelectionValid = !customPeriodRequested || Boolean(
    periodStartDate && periodEndDate && periodStartDate <= periodEndDate && reportingTimezone.trim(),
  );

  const missingTotal = columns.reduce((total, column) => total + Number(profileFor(column, profiles.statistics, profiles.missing).missing || 0), 0);
  const metricLabel = t[operation];
  const metricCompatible = Boolean(version?.id && (
    operation === "count" || operation === "distinct_count" && columns.includes(effectiveValueColumn) ||
    operation === "date_aggregate" && dateColumns.includes(dateColumn) && periodSelectionValid && (!operationNeedsNumeric || numericColumns.includes(effectiveValueColumn)) ||
    numericColumns.includes(effectiveValueColumn)
  ));

  const runExplore = async (offset = 0) => {
    if (!selectedDatasetId || !version?.id) return;
    setExploreStatus("loading");
    setExploreError("");
    const filters = filterColumn ? [{ field: filterColumn, operator: filterOperator,
      ...(["missing", "not_missing"].includes(filterOperator) ? {} : { value: filterValue }) }] : [];
    const sort = sortColumn ? [{ field: sortColumn, direction: sortDirection }] : [];
    try {
      const response = await apiFetch(
        `${projectRoot}/datasets/${encodeURIComponent(selectedDatasetId)}/versions/${encodeURIComponent(version.id)}/explore`,
        { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ columns: [], filters, sort, limit: 50, offset }) },
      );
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      setExploration(body);
      setExploreStatus("ready");
    } catch (requestError) {
      setExploreStatus("error");
      setExploreError(requestError.message || t.loadError);
    }
  };

  const runMetric = async () => {
    if (!metricCompatible || !selectedDatasetId || !version?.id) {
      setMetricError(t.incompatible);
      return;
    }
    const requestId = metricRequestRef.current + 1;
    metricRequestRef.current = requestId;
    const selectionIdentity = `${selectedDatasetId}:${version.id}`;
    setMetricStatus("loading");
    setMetricError("");
    setMetricResult(null);
    const metric = { operation, label: metricLabel };
    if (operationNeedsValue) metric.value_column = effectiveValueColumn;
    if (groupColumn) metric.group_column = groupColumn;
    if (operation === "date_aggregate") {
      metric.date_column = dateColumn;
      metric.period = period;
      metric.aggregation = aggregation;
      metric.timezone = reportingTimezone.trim() || "UTC";
      if (periodStartDate && periodEndDate) {
        metric.start_date = periodStartDate;
        metric.end_date = periodEndDate;
      }
    }
    try {
      const response = await apiFetch(
        `${userRoot}/analysis/projects/${encodeURIComponent(projectId)}/datasets/${encodeURIComponent(selectedDatasetId)}/versions/${encodeURIComponent(version.id)}/assist`,
        {
          method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ metric, language: activeLang, cleaning_actions: [], symbols: {} }),
        },
      );
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, "The calculation could not be completed."));
      if (metricRequestRef.current !== requestId || `${selectedDatasetId}:${selectedVersionId}` !== selectionIdentity) return;
      setMetricResult({ report: body.result || body, provenance: body.provenance || null, metric });
      setMetricStatus("ready");
    } catch (requestError) {
      if (metricRequestRef.current !== requestId) return;
      setMetricStatus("error");
      setMetricError(requestError.message || "The calculation could not be completed.");
    }
  };

  const createDashboard = async () => {
    const name = dashboardName.trim() || `${selectedRegistryDataset?.display_name || t.title} dashboard`;
    setDashboardError("");
    try {
      const response = await apiFetch(`${projectRoot}/dashboards`, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description: dashboardDescription }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      await loadDashboards();
      setSelectedDashboardId(body.id);
    } catch (requestError) { setDashboardError(requestError.message || t.loadError); }
  };

  const saveDashboard = async () => {
    if (!dashboard) return;
    try {
      const response = await apiFetch(`${projectRoot}/dashboards/${encodeURIComponent(dashboard.id)}`, {
        method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: dashboard.revision, name: dashboardName, description: dashboardDescription }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      setDashboard((current) => ({ ...current, ...body })); await loadDashboards();
    } catch (requestError) { setDashboardError(requestError.message || t.loadError); }
  };

  const deleteDashboard = async () => {
    if (!dashboard || !window.confirm(t.deleteDashboard)) return;
    try {
      const response = await apiFetch(`${projectRoot}/dashboards/${encodeURIComponent(dashboard.id)}`, {
        method: "DELETE", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: dashboard.revision }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      setDashboard(null); setSelectedDashboardId(""); await loadDashboards();
    } catch (requestError) { setDashboardError(requestError.message || t.loadError); }
  };

  const addCurrentWidget = async () => {
    if (!dashboard || !metricResult || !version?.id) return;
    const widgetType = chart ? (chart.type === "line" ? "line" : "bar") : (report?.kpis?.length ? "kpi" : "table");
    try {
      const response = await apiFetch(`${projectRoot}/dashboards/${encodeURIComponent(dashboard.id)}/widgets`, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: dashboard.revision, widget_type: widgetType,
          title: resultMetricLabel, dataset_id: selectedDatasetId, dataset_version_id: version.id,
          version_policy: versionPolicy, analysis_spec: metricResult.metric,
          layout_config: { x: 0, y: 0, w: widgetWidth, h: widgetHeight },
          display_options: { show_table: true, show_legend: true } }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      setDashboard((current) => ({ ...current, ...body.dashboard, widgets: [...(current.widgets || []), body.widget] }));
      setWidgetResults((current) => ({ ...current, [body.widget.id]: { status: "ready", result: report,
        provenance: metricResult.provenance } }));
      await loadDashboards();
    } catch (requestError) { setDashboardError(requestError.message || t.loadError); }
  };

  const saveWidget = async (widget, draft) => {
    setDashboardError("");
    try {
      const response = await apiFetch(`${projectRoot}/dashboards/${encodeURIComponent(dashboard.id)}/widgets/${encodeURIComponent(widget.id)}`, {
        method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: dashboard.revision,
          widget_type: draft.widget_type, title: draft.title.trim(), dataset_id: widget.dataset_id,
          dataset_version_id: widget.dataset_version_id, version_policy: widget.version_policy,
          analysis_spec: widget.analysis_spec, layout_config: draft.layout_config,
          display_options: draft.display_options }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      setDashboard((current) => ({ ...current, ...body.dashboard,
        widgets: current.widgets.map((item) => item.id === widget.id ? body.widget : item) }));
      await loadDashboards();
    } catch (requestError) { setDashboardError(requestError.message || t.loadError); }
  };

  const executeWidget = async (widget, refreshLatest) => {
    try {
      const response = await apiFetch(`${projectRoot}/dashboards/${encodeURIComponent(dashboard.id)}/widgets/${encodeURIComponent(widget.id)}/execute`, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_latest: refreshLatest, language: activeLang }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      setWidgetResults((current) => ({ ...current, [widget.id]: body }));
      if (body.dashboard_revision) setDashboard((current) => ({ ...current, revision: body.dashboard_revision,
        widgets: current.widgets.map((item) => item.id === widget.id ? body.widget : item) }));
    } catch (requestError) { setDashboardError(requestError.message || t.loadError); }
  };

  const removeWidget = async (widget) => {
    if (!window.confirm(t.removeWidget)) return;
    try {
      const response = await apiFetch(`${projectRoot}/dashboards/${encodeURIComponent(dashboard.id)}/widgets/${encodeURIComponent(widget.id)}`, {
        method: "DELETE", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: dashboard.revision }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      setDashboard((current) => ({ ...current, ...body, widgets: current.widgets.filter((item) => item.id !== widget.id) }));
    } catch (requestError) { setDashboardError(requestError.message || t.loadError); }
  };

  const configureAutomaticRefresh = async (enabled) => {
    if (!dashboard) return;
    setDashboardError("");
    try {
      const response = await apiFetch(`${projectRoot}/dashboards/${encodeURIComponent(dashboard.id)}/automatic-refresh`, {
        method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: dashboard.revision, enabled }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      setDashboard((current) => ({ ...current, ...body }));
      await loadDashboards();
    } catch (requestError) { setDashboardError(requestError.message || t.loadError); }
  };

  const shareDashboard = async () => {
    if (!dashboard?.access?.is_owner || !dashboardShareMember) return;
    setDashboardError("");
    try {
      const response = await apiFetch(`${projectRoot}/dashboards/${encodeURIComponent(dashboard.id)}/shares/${encodeURIComponent(dashboardShareMember)}`, {
        method: "PUT", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: dashboard.revision, member_user_id: Number(dashboardShareMember), permission: dashboardSharePermission }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      setDashboard((current) => ({ ...current, revision: body.dashboard?.revision ?? current.revision }));
      setDashboardShareMember("");
      const sharesResponse = await apiFetch(`${projectRoot}/dashboards/${encodeURIComponent(dashboard.id)}/shares`, { credentials: "include" });
      const sharesBody = await readApiResponse(sharesResponse);
      if (!sharesResponse.ok) throw new Error(detailMessage(sharesBody, t.loadError));
      setDashboardShares(Array.isArray(sharesBody.items) ? sharesBody.items : []);
      setDashboardMembers(Array.isArray(sharesBody.members) ? sharesBody.members : []);
    } catch (requestError) { setDashboardError(requestError.message || t.loadError); }
  };

  const revokeDashboardShare = async (share) => {
    if (!dashboard?.access?.is_owner) return;
    setDashboardError("");
    try {
      const response = await apiFetch(`${projectRoot}/dashboards/${encodeURIComponent(dashboard.id)}/shares/${encodeURIComponent(share.member_user_id)}`, {
        method: "DELETE", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: dashboard.revision, member_user_id: Number(share.member_user_id) }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      setDashboard((current) => ({ ...current, revision: body.dashboard?.revision ?? current.revision }));
      setDashboardShares((current) => current.filter((item) => Number(item.member_user_id) !== Number(share.member_user_id)));
    } catch (requestError) { setDashboardError(requestError.message || t.loadError); }
  };

  const createSchedule = async () => {
    if (!selectedDashboardId) return;
    setReportError("");
    const payload = {
      dashboard_id: selectedDashboardId,
      name: scheduleName.trim() || dashboard?.name || t.reportsTitle,
      cadence: scheduleCadence,
      timezone: scheduleTimezone,
      local_time: scheduleTime,
      weekday: scheduleCadence === "weekly" ? Number(scheduleWeekday) : null,
      month_day: scheduleCadence === "monthly" ? Number(scheduleMonthDay) : null,
      enabled: scheduleEnabled,
      require_ready_checkpoints: false,
    };
    try {
      const editing = schedules.find((item) => item.id === editingScheduleId);
      const response = await apiFetch(`${projectRoot}/report-schedules${editing ? `/${encodeURIComponent(editing.id)}` : ""}`, {
        method: editing ? "PATCH" : "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(editing ? { ...payload, expected_revision: editing.revision } : payload),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      setScheduleName(""); setEditingScheduleId(""); setScheduleEnabled(true); await loadReports();
    } catch (requestError) { setReportError(requestError.message || t.loadError); }
  };

  const beginScheduleEdit = (schedule) => {
    setEditingScheduleId(schedule.id); setScheduleName(schedule.name); setScheduleCadence(schedule.cadence);
    setScheduleTimezone(schedule.timezone); setScheduleTime(String(schedule.local_time || "09:00").slice(0, 5));
    setScheduleWeekday(schedule.weekday ?? 0); setScheduleMonthDay(schedule.month_day ?? 1);
    setScheduleEnabled(Boolean(schedule.enabled));
  };

  const openDeliveryConfig = async (schedule) => {
    setReportError("");
    try {
      const response = await apiFetch(`${projectRoot}/report-schedules/${encodeURIComponent(schedule.id)}/delivery`, { credentials: "include" });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      setDeliveryAvailable(body.available !== false);
      if (body.available === false) return;
      setDeliverySchedule(schedule);
      setDeliveryEnabled(Boolean(body.config?.enabled));
      setDeliveryMembers(Array.isArray(body.members) ? body.members : []);
      setDeliveryRecipients(Array.isArray(body.recipient_user_ids) ? body.recipient_user_ids.map(Number) : []);
    } catch (requestError) { setReportError(requestError.message || t.loadError); }
  };

  const saveDeliveryConfig = async () => {
    if (!deliverySchedule) return;
    setReportError("");
    try {
      const response = await apiFetch(`${projectRoot}/report-schedules/${encodeURIComponent(deliverySchedule.id)}/delivery`, {
        method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_schedule_revision: deliverySchedule.revision,
          enabled: deliveryEnabled, recipient_user_ids: deliveryRecipients }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      const updatedSchedule = body.schedule || deliverySchedule;
      setDeliverySchedule(updatedSchedule);
      setSchedules((current) => current.map((item) => item.id === updatedSchedule.id ? { ...item, ...updatedSchedule } : item));
    } catch (requestError) { setReportError(requestError.message || t.loadError); }
  };

  const saveLifecycle = async () => {
    setReportError("");
    try {
      const response = await apiFetch(`${projectRoot}/report-lifecycle`, {
        method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: lifecycleSettings.revision || null,
          retention_days: Number(lifecycleSettings.retention_days), cleanup_enabled: Boolean(lifecycleSettings.cleanup_enabled) }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      setLifecycleSettings(body);
    } catch (requestError) { setReportError(requestError.message || t.loadError); }
  };

  const generateReport = async () => {
    if (!selectedDashboardId) return;
    setReportError("");
    try {
      const response = await apiFetch(`${projectRoot}/reports`, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dashboard_id: selectedDashboardId }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      await loadReports();
    } catch (requestError) { setReportError(requestError.message || t.loadError); }
  };

  const removeSchedule = async (schedule) => {
    if (!window.confirm(t.removeSchedule)) return;
    setReportError("");
    try {
      const response = await apiFetch(`${projectRoot}/report-schedules/${encodeURIComponent(schedule.id)}`, {
        method: "DELETE", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: schedule.revision }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      await loadReports();
    } catch (requestError) { setReportError(requestError.message || t.loadError); }
  };

  const retryReport = async (reportId) => {
    setReportError("");
    try {
      const response = await apiFetch(`${projectRoot}/reports/${encodeURIComponent(reportId)}/retry`, {
        method: "POST", credentials: "include",
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      await loadReports();
    } catch (requestError) { setReportError(requestError.message || t.loadError); }
  };

  const archiveReport = async (reportId) => {
    if (!window.confirm(t.archiveReport)) return;
    setReportError("");
    try {
      const response = await apiFetch(`${projectRoot}/reports/${encodeURIComponent(reportId)}`, {
        method: "DELETE", credentials: "include",
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      if (selectedReport?.id === reportId) setSelectedReport(null);
      await loadReports();
    } catch (requestError) { setReportError(requestError.message || t.loadError); }
  };

  const openReport = async (reportId) => {
    setReportError("");
    try {
      const response = await apiFetch(`${projectRoot}/reports/${encodeURIComponent(reportId)}`, { credentials: "include" });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      const normalized = { ...body, access: body.access || { is_owner: true, permission: "owner", can_edit: true, can_share: true } };
      setSelectedReport(normalized);
      setDeliveryHistory([]);
      setReportShares([]);
      setReportMembers([]);
      setReportShareMember("");
      if (normalized.access.is_owner && sharingAvailable) {
        const sharesResponse = await apiFetch(`${projectRoot}/reports/${encodeURIComponent(reportId)}/shares`, { credentials: "include" });
        const sharesBody = await readApiResponse(sharesResponse);
        if (!sharesResponse.ok) throw new Error(detailMessage(sharesBody, t.loadError));
        setReportShares(Array.isArray(sharesBody.items) ? sharesBody.items : []);
        setReportMembers(Array.isArray(sharesBody.members) ? sharesBody.members : []);
      }
      if (normalized.access.is_owner && deliveryAvailable) {
        const deliveriesResponse = await apiFetch(`${projectRoot}/reports/${encodeURIComponent(reportId)}/deliveries`, { credentials: "include" });
        const deliveriesBody = await readApiResponse(deliveriesResponse);
        if (!deliveriesResponse.ok) throw new Error(detailMessage(deliveriesBody, t.loadError));
        setDeliveryAvailable(deliveriesBody.available !== false);
        setDeliveryHistory(Array.isArray(deliveriesBody.items) ? deliveriesBody.items : []);
      }
    } catch (requestError) { setReportError(requestError.message || t.loadError); }
  };

  const shareReport = async () => {
    if (!selectedReport?.access?.is_owner || !reportShareMember) return;
    setReportError("");
    try {
      const response = await apiFetch(`${projectRoot}/reports/${encodeURIComponent(selectedReport.id)}/shares/${encodeURIComponent(reportShareMember)}`, {
        method: "PUT", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member_user_id: Number(reportShareMember), permission: "viewer" }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      setReportShareMember("");
      const sharesResponse = await apiFetch(`${projectRoot}/reports/${encodeURIComponent(selectedReport.id)}/shares`, { credentials: "include" });
      const sharesBody = await readApiResponse(sharesResponse);
      if (!sharesResponse.ok) throw new Error(detailMessage(sharesBody, t.loadError));
      setReportShares(Array.isArray(sharesBody.items) ? sharesBody.items : []);
      setReportMembers(Array.isArray(sharesBody.members) ? sharesBody.members : []);
    } catch (requestError) { setReportError(requestError.message || t.loadError); }
  };

  const revokeReportShare = async (share) => {
    if (!selectedReport?.access?.is_owner) return;
    setReportError("");
    try {
      const response = await apiFetch(`${projectRoot}/reports/${encodeURIComponent(selectedReport.id)}/shares/${encodeURIComponent(share.member_user_id)}`, {
        method: "DELETE", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ member_user_id: Number(share.member_user_id), expected_share_revision: share.revision }),
      });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(detailMessage(body, t.loadError));
      setReportShares((current) => current.filter((item) => Number(item.member_user_id) !== Number(share.member_user_id)));
    } catch (requestError) { setReportError(requestError.message || t.loadError); }
  };

  const report = metricResult?.report;
  const resultRows = report?.tables?.[0]?.rows || [];
  const chart = report?.charts?.[0] || null;
  const resultMetricLabel = metricResult?.metric?.label || metricLabel;
  const selectedDashboardSummary = dashboards.find((item) => item.id === selectedDashboardId) || null;
  const selectedDashboardOwned = selectedDashboardSummary?.access?.is_owner !== false;
  if (status === "loading") return <main className="bi-workspace" dir={activeLang === "ar" ? "rtl" : "ltr"}><StatePanel title={t.loading} /></main>;
  if (status === "error") return <main className="bi-workspace" dir={activeLang === "ar" ? "rtl" : "ltr"}><StatePanel icon={AlertTriangle} role="alert" title={t.loadError} action={<button type="button" onClick={loadDatasets}>{t.retry}</button>}>{error}</StatePanel></main>;
  if (!available) return <main className="bi-workspace" dir={activeLang === "ar" ? "rtl" : "ltr"}><StatePanel title={t.unavailable}>{t.unavailableHint}</StatePanel></main>;

  return (
    <main className="bi-workspace" dir={activeLang === "ar" ? "rtl" : "ltr"}>
      <header className="bi-header">
        <div><span>PROJECT BI</span><h1>{t.title}</h1><p>{t.subtitle}</p></div>
        <button type="button" className="bi-secondary" onClick={onChangeProject}><FolderOpen size={17} aria-hidden="true" />{t.changeProject}</button>
      </header>

      {!datasets.length ? <StatePanel title={t.empty}>{t.emptyHint}</StatePanel> : (
        <>
          <section className="bi-context" aria-label={t.provenance}>
            <label>{t.dataset}<select aria-label={t.dataset} value={selectedDatasetId} onChange={(event) => {
              metricRequestRef.current += 1;
              setMetricResult(null);
              setMetricError("");
              setMetricStatus("idle");
              setFilterColumn("");
              setFilterValue("");
              setSortColumn("");
              setSelectedDatasetId(event.target.value);
            }}>{datasets.map((item) => <option key={item.id} value={item.id}>{item.display_name}</option>)}</select></label>
            <label>{t.version}<select aria-label={t.version} value={selectedVersionId} onChange={(event) => {
              metricRequestRef.current += 1; setMetricResult(null); setMetricStatus("idle");
              setSelectedVersionId(event.target.value);
            }}>{versions.map((item) => <option key={item.id} value={item.id}>v{item.version_number} · {item.version_kind || "committed"}</option>)}</select></label>
            <p><Database size={16} aria-hidden="true" />{t.versionBound}</p>
          </section>

          <nav className="bi-tabs" aria-label={t.title}>
            <div role="tablist">
              {t.tabs.map((label, index) => {
                const id = COPY.en.tabs[index];
                const panelId = `bi-${id.toLowerCase()}-panel`;
                return <button type="button" role="tab" id={`${panelId}-tab`} aria-controls={panelId} aria-selected={tab === id} key={id} onClick={() => setTab(id)}>{label}</button>;
              })}
            </div>
          </nav>

          {tab === "Overview" && (
            <section className="bi-panel" id="bi-overview-panel" role="tabpanel" aria-labelledby="bi-overview-panel-tab">
              <div className="bi-panel-heading"><div><span>OVERVIEW</span><h2 id="bi-overview-title">{selectedRegistryDataset?.display_name}</h2></div><CheckCircle2 size={24} aria-hidden="true" /></div>
              <div className="bi-stat-grid">
                <article><span>{t.rows}</span><strong>{dataset?.rows ?? version?.file_metadata?.rows ?? "—"}</strong></article>
                <article><span>{t.columns}</span><strong>{columns.length || version?.file_metadata?.column_count || "—"}</strong></article>
                <article><span>{t.missing}</span><strong>{profileStatus === "loading" ? "…" : missingTotal}</strong></article>
                <article><span>{t.updated}</span><strong>{formatDate(selectedRegistryDataset?.updated_at || version?.created_at, activeLang)}</strong></article>
              </div>
              <div className="bi-provenance-grid">
                <article><span>{t.source}</span><strong>{freshness?.source ? `${freshness.source.display_name || "—"} · ${freshness.source.status || freshness.source.sync_state || "—"}` : t.sourceUnavailable}</strong></article>
                <article><span>{t.lastEvent}</span><strong>{freshness?.webhook?.last_received_at ? formatDate(freshness.webhook.last_received_at, activeLang) : t.syncUnavailable}</strong></article>
                <article><span>{t.lastAttempt}</span><strong>{freshness?.source?.last_ingestion_attempt ? formatDate(freshness.source.last_ingestion_attempt, activeLang) : t.syncUnavailable}</strong></article>
                <article><span>{t.sync}</span><strong>{freshness?.source?.last_successful_ingestion ? formatDate(freshness.source.last_successful_ingestion, activeLang) : t.syncUnavailable}</strong></article>
                <article><span>{t.checkpoint}</span><strong>{freshness?.checkpoint ? `${freshness.checkpoint.status} · r${freshness.checkpoint.target_revision}` : t.syncUnavailable}</strong></article>
                <article><span>{t.reconciliation}</span><strong>{freshness?.resource?.pending_reconciliation ? t.pending : t.current}</strong></article>
                <article><span>{t.contentHash}</span><code dir="ltr">{version?.content_hash || t.noHash}</code></article>
              </div>
              <aside className="bi-notice"><Gauge size={20} aria-hidden="true" /><div><strong>{t.semanticTitle}</strong><p>{t.semanticHint}</p></div></aside>
            </section>
          )}

          {tab === "Explore" && (
            <section className="bi-panel" id="bi-explore-panel" role="tabpanel" aria-labelledby="bi-explore-panel-tab">
              <div className="bi-panel-heading"><div><span>EXPLORE</span><h2 id="bi-explore-title">{t.preview}</h2><p>{t.previewLimit}</p></div><Table2 size={24} aria-hidden="true" /></div>
              <div className="bi-explore-tools">
                <label><span>{t.filter}</span><select aria-label={t.filter} value={filterColumn} onChange={(event) => setFilterColumn(event.target.value)}><option value="">{t.none}</option>{columns.map((column) => <option key={column}>{column}</option>)}</select></label>
                <label><span>{t.filterOperator}</span><select aria-label={t.filterOperator} value={filterOperator} onChange={(event) => setFilterOperator(event.target.value)}>{["eq", "gte", "lte", "missing", "not_missing"].map((item) => <option key={item}>{item}</option>)}</select></label>
                {!(["missing", "not_missing"].includes(filterOperator)) ? <label><Search size={16} aria-hidden="true" /><span>{t.filterValue}</span><input aria-label={t.filterValue} value={filterValue} onChange={(event) => setFilterValue(event.target.value)} /></label> : null}
                <label><span>{t.sort}</span><select aria-label={t.sort} value={sortColumn} onChange={(event) => setSortColumn(event.target.value)}><option value="">{t.none}</option>{columns.map((column) => <option key={column}>{column}</option>)}</select></label>
                <label><span>Direction</span><select aria-label="Direction" value={sortDirection} onChange={(event) => setSortDirection(event.target.value)}><option value="asc">asc</option><option value="desc">desc</option></select></label>
                <button type="button" onClick={() => void runExplore(0)} disabled={exploreStatus === "loading"}>{t.apply}</button>
              </div>
              {exploreError ? <p className="bi-error" role="alert">{exploreError}</p> : null}
              {previewRows.length ? <ResultTable rows={previewRows} /> : <p className="bi-empty-inline">{t.noRows}</p>}
              <div className="bi-pagination"><button type="button" disabled={!exploration?.pagination?.offset} onClick={() => void runExplore(Math.max(0, exploration.pagination.offset - exploration.pagination.limit))}>{t.previous}</button><span>{exploration?.pagination ? `${exploration.pagination.offset + 1}–${exploration.pagination.offset + exploration.pagination.returned} / ${exploration.pagination.total}` : "—"}</span><button type="button" disabled={!exploration?.pagination?.has_more} onClick={() => void runExplore(exploration.pagination.offset + exploration.pagination.limit)}>{t.next}</button></div>
              <h3>{t.quality}</h3><p className="bi-muted">{t.qualityHint}</p>
              {profileStatus === "error" || profileStatus === "partial" ? <p role="status" className="bi-warning">{t.missingProfile}</p> : null}
              <div className="bi-table-scroll"><table className="bi-table"><thead><tr><th>{t.column}</th><th>{t.type}</th><th>{t.filled}</th><th>{t.missing}</th><th>{t.unique}</th></tr></thead><tbody>{columns.map((column) => { const profile = profileFor(column, profiles.statistics, profiles.missing); return <tr key={column}><th scope="row" dir="auto">{column}</th><td>{profileType(column, profiles.types, profiles.statistics)}</td><td>{profile.count ?? "—"}</td><td>{profile.missing} ({formatNumber(Number(profile.missingPercentage || 0), activeLang)}%)</td><td>{profile.unique ?? "—"}</td></tr>; })}</tbody></table></div>
            </section>
          )}

          {tab === "Metrics" && (
            <section className="bi-panel" id="bi-metrics-panel" role="tabpanel" aria-labelledby="bi-metrics-panel-tab">
              <div className="bi-panel-heading"><div><span>METRICS</span><h2 id="bi-metrics-title">{t.operation}</h2><p>{t.metricIntro}</p></div><Gauge size={24} aria-hidden="true" /></div>
              <div className="bi-metric-form">
                <label>{t.operation}<select value={operation} onChange={(event) => setOperation(event.target.value)}>{OPERATIONS.map((item) => <option key={item} value={item}>{t[item]}</option>)}</select></label>
                {operationNeedsValue ? <label>{operation === "distinct_count" ? t.distinctColumn : t.valueColumn}<select value={effectiveValueColumn} onChange={(event) => setValueColumn(event.target.value)}><option value="">{t.select}</option>{(operation === "distinct_count" ? columns : numericColumns).map((column) => <option key={column}>{column}</option>)}</select></label> : null}
                {operation === "date_aggregate" ? <><label>{t.dateColumn}<select value={dateColumn} onChange={(event) => setDateColumn(event.target.value)}><option value="">{t.select}</option>{dateColumns.map((column) => <option key={column}>{column}</option>)}</select></label><label>{t.period}<select value={period} onChange={(event) => setPeriod(event.target.value)}><option value="day">day</option><option value="week">week</option><option value="month">month</option></select></label><label>{t.aggregation}<select value={aggregation} onChange={(event) => setAggregation(event.target.value)}>{["count", "sum", "mean", "min", "max"].map((item) => <option key={item}>{item}</option>)}</select></label><fieldset className="bi-period-controls"><legend>{t.customPeriod}</legend><label>{t.startDate}<DateTimeInput aria-label={t.startDate} type="date" dir="ltr" value={periodStartDate} onChange={(event) => setPeriodStartDate(event.target.value)} /></label><label>{t.endDate}<DateTimeInput aria-label={t.endDate} type="date" dir="ltr" value={periodEndDate} onChange={(event) => setPeriodEndDate(event.target.value)} /></label><label>{t.reportingTimezone}<input aria-label={t.reportingTimezone} dir="ltr" value={reportingTimezone} onChange={(event) => setReportingTimezone(event.target.value)} /></label></fieldset></> : <label>{t.groupColumn}<select value={groupColumn} onChange={(event) => setGroupColumn(event.target.value)}><option value="">{t.none}</option>{columns.map((column) => <option key={column}>{column}</option>)}</select></label>}
                <button type="button" disabled={!metricCompatible || metricStatus === "loading"} onClick={runMetric}>{metricStatus === "loading" ? <RefreshCw className="is-spinning" size={17} aria-hidden="true" /> : <Gauge size={17} aria-hidden="true" />}{metricStatus === "loading" ? t.running : t.run}</button>
              </div>
              {!periodSelectionValid ? <p className="bi-warning" role="status">{t.periodInvalid}</p> : operation === "date_aggregate" && !dateColumns.length ? <p className="bi-warning" role="status">{t.dateSemanticsUnavailable}</p> : !metricCompatible ? <p className="bi-warning" role="status">{t.incompatible}</p> : null}
              {metricError ? <p className="bi-error" role="alert">{metricError}</p> : null}
              {report ? <article className="bi-result"><header><div><span>{t.result}</span><h3>{resultMetricLabel}</h3></div>{report.kpis?.[0] ? <strong>{report.kpis[0].display_value ?? formatNumber(report.kpis[0].value, activeLang)}</strong> : null}</header><p>{report.summary}</p><small>{t.unknownUnit}</small><ResultTable rows={resultRows} /><PeriodDisclosure report={report} copy={t} /><details><summary>{t.provenance}</summary><dl><div><dt>project_id</dt><dd>{metricResult.provenance?.project_id || projectId}</dd></div><div><dt>dataset_id</dt><dd>{metricResult.provenance?.dataset_id || selectedDatasetId}</dd></div><div><dt>dataset_version_id</dt><dd>{metricResult.provenance?.dataset_version_id || version?.id}</dd></div><div><dt>content_hash</dt><dd>{metricResult.provenance?.content_hash || version?.content_hash || t.noHash}</dd></div><div><dt>operation</dt><dd>{metricResult.metric?.operation}</dd></div></dl></details></article> : <p className="bi-empty-inline">{t.noResult}</p>}
            </section>
          )}

          {tab === "Visualizations" && (
            <section className="bi-panel" id="bi-visualizations-panel" role="tabpanel" aria-labelledby="bi-visualizations-panel-tab">
              <div className="bi-panel-heading"><div><span>VISUALIZATIONS</span><h2 id="bi-visual-title">{t.chartTitle}</h2><p>{t.chartHint}</p></div><BarChart3 size={24} aria-hidden="true" /></div>
              {chart ? <AccessibleChart chart={chart} lang={activeLang} emptyLabel={t.chartEmpty} legendLabel={t.chartLegend} /> : <StatePanel icon={BarChart3} title={t.chartTitle}>{t.chartUnavailable}</StatePanel>}
            </section>
          )}

          {tab === "Dashboard" && (
            <section className="bi-panel" id="bi-dashboard-panel" role="tabpanel" aria-labelledby="bi-dashboard-panel-tab">
              <div className="bi-panel-heading"><div><span>DASHBOARD</span><h2 id="bi-dashboard-title">{t.dashboardTitle}</h2><p>{t.dashboardHint}</p></div><LayoutDashboard size={24} aria-hidden="true" /></div>
              {!dashboardsAvailable ? <aside className="bi-notice is-warning"><AlertTriangle size={20} aria-hidden="true" /><div><strong>{t.persistenceUnavailable}</strong><p>{t.semanticHint}</p></div></aside> : <>
                {dashboardError ? <p className="bi-error" role="alert">{dashboardError}</p> : null}
                <div className="bi-dashboard-controls">
                  <label>{t.dashboardTitle}<select aria-label={t.dashboardTitle} value={selectedDashboardId} onChange={(event) => { setDashboard(null); setSelectedDashboardId(event.target.value); }}><option value="">{t.noDashboards}</option>{dashboards.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
                  {!dashboard || dashboard.access?.can_edit ? <label>{t.dashboardName}<input aria-label={t.dashboardName} value={dashboardName} onChange={(event) => setDashboardName(event.target.value)} /></label> : null}
                  {!dashboard || dashboard.access?.can_edit ? <label>{t.dashboardDescription}<input aria-label={t.dashboardDescription} value={dashboardDescription} onChange={(event) => setDashboardDescription(event.target.value)} /></label> : null}
                  {!dashboard ? <button type="button" onClick={() => void createDashboard()}>{t.createDashboard}</button> : <>{dashboard.access?.can_edit ? <button type="button" onClick={() => void saveDashboard()}>{t.saveDashboard}</button> : null}{dashboard.access?.is_owner ? <button type="button" className="is-danger" onClick={() => void deleteDashboard()}>{t.deleteDashboard}</button> : null}</>}
                </div>
                {dashboard ? <>
                  {!dashboard.access?.is_owner ? <p className="bi-notice" role="status"><strong>{dashboard.access?.permission === "editor" ? t.sharedEditor : t.sharedViewer}</strong> · {t.ownerOnly}</p> : null}
                  {dashboard.access?.is_owner ? <label className="bi-auto-refresh"><input type="checkbox" checked={Boolean(dashboard.auto_refresh_enabled)} disabled={!reportingAvailable} onChange={(event) => void configureAutomaticRefresh(event.target.checked)} /><span><strong>{t.autoRefresh}</strong><small>{reportingAvailable ? t.autoRefreshHint : t.reportingUnavailable}</small></span></label> : null}
                  {dashboard.access?.is_owner ? <div className="bi-widget-add"><label>Version policy<select aria-label="Version policy" value={versionPolicy} onChange={(event) => setVersionPolicy(event.target.value)}><option value="pinned">{t.pinned}</option><option value="latest_committed">{t.latest_committed}</option></select></label><label>{t.widgetWidth}<select aria-label={t.widgetWidth} value={widgetWidth} onChange={(event) => setWidgetWidth(Number(event.target.value))}>{[3, 4, 6, 8, 12].map((item) => <option key={item} value={item}>{item}/12</option>)}</select></label><label>{t.widgetHeight}<select aria-label={t.widgetHeight} value={widgetHeight} onChange={(event) => setWidgetHeight(Number(event.target.value))}>{[3, 4, 6, 8].map((item) => <option key={item} value={item}>{item}</option>)}</select></label><button type="button" disabled={!metricResult} onClick={() => void addCurrentWidget()}>{t.addWidget}</button></div> : null}
                  {(dashboard.widgets || []).length ? <div className="bi-widget-grid">{dashboard.widgets.map((widget) => <DashboardWidget
                    key={widget.id} widget={widget} execution={widgetResults[widget.id]} lang={activeLang} copy={t}
                    canEdit={Boolean(dashboard.access?.can_edit)}
                    onSave={(draft) => void saveWidget(widget, draft)}
                    onRefresh={() => void executeWidget(widget, true)} onRemove={() => void removeWidget(widget)}
                  />)}</div> : <p className="bi-empty-inline">{t.noWidgets}</p>}
                  {dashboard.access?.is_owner ? (sharingAvailable ? <SharingPanel copy={t} members={dashboardMembers} shares={dashboardShares}
                    selectedMemberId={dashboardShareMember} permission={dashboardSharePermission}
                    onMemberChange={setDashboardShareMember} onPermissionChange={setDashboardSharePermission}
                    onShare={() => void shareDashboard()} onRevoke={(share) => void revokeDashboardShare(share)} />
                    : <aside className="bi-notice is-warning"><AlertTriangle size={20} aria-hidden="true" /><div><strong>{t.sharingUnavailable}</strong></div></aside>) : null}
                </> : null}
              </>}
            </section>
          )}

          {tab === "Reports" && (
            <section className="bi-panel" id="bi-reports-panel" role="tabpanel" aria-labelledby="bi-reports-panel-tab">
              <div className="bi-panel-heading"><div><span>REPORTS</span><h2>{t.reportsTitle}</h2><p>{t.reportsHint}</p></div><FileText size={24} aria-hidden="true" /></div>
              {!reportingAvailable ? <aside className="bi-notice is-warning"><AlertTriangle size={20} aria-hidden="true" /><div><strong>{t.reportingUnavailable}</strong><p>{t.semanticHint}</p></div></aside> : <>
                {reportError ? <p className="bi-error" role="alert">{reportError}</p> : null}
                <div className="bi-report-controls">
                  <label>{t.dashboardTitle}<select value={selectedDashboardId} onChange={(event) => setSelectedDashboardId(event.target.value)}><option value="">{t.noDashboards}</option>{dashboards.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
                  <button type="button" disabled={!selectedDashboardId || !selectedDashboardOwned} onClick={() => void generateReport()}><FileText size={16} aria-hidden="true" />{t.generateNow}</button>
                </div>
                {selectedDashboardOwned ? <form className="bi-schedule-form" onSubmit={(event) => { event.preventDefault(); void createSchedule(); }}>
                  <label>{t.scheduleName}<input value={scheduleName} onChange={(event) => setScheduleName(event.target.value)} /></label>
                  <label>{t.cadence}<select value={scheduleCadence} onChange={(event) => setScheduleCadence(event.target.value)}><option value="daily">daily</option><option value="weekly">weekly</option><option value="monthly">monthly</option></select></label>
                  <label>{t.timezone}<input value={scheduleTimezone} onChange={(event) => setScheduleTimezone(event.target.value)} /></label>
                  <label>{t.localTime}<DateTimeInput type="time" value={scheduleTime} onChange={(event) => setScheduleTime(event.target.value)} /></label>
                  {scheduleCadence === "weekly" ? <label>{t.weekday}<input type="number" min="0" max="6" value={scheduleWeekday} onChange={(event) => setScheduleWeekday(event.target.value)} /></label> : null}
                  {scheduleCadence === "monthly" ? <label>{t.monthDay}<input type="number" min="1" max="31" value={scheduleMonthDay} onChange={(event) => setScheduleMonthDay(event.target.value)} /></label> : null}
                  <label className="bi-schedule-enabled"><input type="checkbox" checked={scheduleEnabled} onChange={(event) => setScheduleEnabled(event.target.checked)} />{t.scheduleEnabled}</label>
                  <button type="submit" disabled={!selectedDashboardId}><CalendarClock size={16} aria-hidden="true" />{editingScheduleId ? t.saveSchedule : t.createSchedule}</button>
                </form> : <p className="bi-notice" role="status">{t.ownerOnly}</p>}
                {deliveryAvailable ? <section className="bi-lifecycle" aria-labelledby="bi-retention-title">
                  <div><h3 id="bi-retention-title">{t.retentionTitle}</h3><p>{t.deliveryHint}</p></div>
                  <label>{t.retentionDays}<input type="number" min="7" max="365" value={lifecycleSettings.retention_days} onChange={(event) => setLifecycleSettings((current) => ({ ...current, retention_days: Number(event.target.value) }))} /></label>
                  <label className="bi-schedule-enabled"><input type="checkbox" checked={Boolean(lifecycleSettings.cleanup_enabled)} onChange={(event) => setLifecycleSettings((current) => ({ ...current, cleanup_enabled: event.target.checked }))} />{t.cleanupEnabled}</label>
                  <button type="button" onClick={() => void saveLifecycle()}>{t.saveRetention}</button>
                </section> : <aside className="bi-notice is-warning"><AlertTriangle size={20} aria-hidden="true" /><div><strong>{t.deliveryUnavailable}</strong></div></aside>}
                <div className="bi-report-grid">
                  <section><h3>{t.createSchedule}</h3>{schedules.length ? <ul className="bi-report-list">{schedules.map((schedule) => <li key={schedule.id}><div><strong>{schedule.name}</strong><small>{schedule.cadence} · {schedule.local_time} · {schedule.timezone} · {schedule.enabled ? t.scheduleEnabled : t.statusLabel}</small><small>{t.nextRun}: {formatDate(schedule.next_run_at, activeLang)}</small></div><div><button type="button" onClick={() => beginScheduleEdit(schedule)}>{t.editSchedule}</button>{deliveryAvailable ? <button type="button" onClick={() => void openDeliveryConfig(schedule)}>{t.configureDelivery}</button> : null}<button type="button" onClick={() => void removeSchedule(schedule)}>{t.removeSchedule}</button></div></li>)}</ul> : <p className="bi-empty-inline">{t.noSchedules}</p>}</section>
                  <section><h3>{t.reportHistory}</h3>{reports.length ? <ul className="bi-report-list">{reports.map((item) => <li key={item.id}><div><strong>{item.trigger_type} · {item.status}</strong><small>{formatDate(item.completed_at || item.created_at, activeLang)} · r{item.dashboard_revision}{item.access?.is_owner === false ? ` · ${t.sharedWithMe}` : ""}</small><small>{(item.version_vector || []).map((entry) => `v${entry.version_number || "—"}`).join(", ") || "—"}</small></div><div>{item.access?.is_owner !== false && ["failed", "needs_attention"].includes(item.status) ? <button type="button" onClick={() => void retryReport(item.id)}>{t.retry}</button> : null}<button type="button" onClick={() => void openReport(item.id)}>{t.openReport}</button></div></li>)}</ul> : <p className="bi-empty-inline">{t.noReports}</p>}</section>
                </div>
                {deliverySchedule ? <section className="bi-delivery-config" aria-labelledby="bi-delivery-title">
                  <div><h3 id="bi-delivery-title">{t.deliveryTitle}: {deliverySchedule.name}</h3><p>{t.deliveryHint}</p></div>
                  <label className="bi-schedule-enabled"><input type="checkbox" checked={deliveryEnabled} onChange={(event) => setDeliveryEnabled(event.target.checked)} />{t.deliveryEnabled}</label>
                  <fieldset><legend>{t.recipients}</legend>{deliveryMembers.map((member) => <label key={member.id}><input type="checkbox" checked={deliveryRecipients.includes(Number(member.id))} onChange={(event) => setDeliveryRecipients((current) => event.target.checked ? [...current, Number(member.id)] : current.filter((id) => id !== Number(member.id)))} /><span>{`${member.first_name || ""} ${member.last_name || ""}`.trim() || member.email} · {member.email}</span></label>)}</fieldset>
                  <button type="button" disabled={deliveryEnabled && !deliveryRecipients.length} onClick={() => void saveDeliveryConfig()}>{t.saveDelivery}</button>
                </section> : null}
                {selectedReport ? <><article className="bi-report-print" aria-live="polite"><header><div><small>{t.statusLabel}: {selectedReport.status}{selectedReport.access?.is_owner === false ? ` · ${t.sharedWithMe}` : ""}</small><h3>{selectedReport.result_snapshot?.title || selectedReport.definition_snapshot?.dashboard?.name || t.reportsTitle}</h3><p>{t.reportDisclosure}</p>{selectedReport.artifact_deleted_at ? <p className="bi-warning">{t.artifactExpired}</p> : null}</div><div className="bi-print-actions">{selectedReport.status === "completed" && !selectedReport.artifact_deleted_at ? <><a className="bi-button" href={`${projectRoot}/reports/${encodeURIComponent(selectedReport.id)}/export.csv`}><Download size={16} aria-hidden="true" />{t.downloadCsv}</a><a className="bi-button" href={`${projectRoot}/reports/${encodeURIComponent(selectedReport.id)}/export.pdf?language=${activeLang}`}><Download size={16} aria-hidden="true" />{t.downloadPdf}</a><a className="bi-button" href={`${projectRoot}/reports/${encodeURIComponent(selectedReport.id)}/export.xlsx?language=${activeLang}`}><Download size={16} aria-hidden="true" />{t.downloadXlsx}</a></> : null}<button type="button" onClick={() => window.print()}>{t.printReport}</button>{selectedReport.access?.is_owner && ["completed", "failed", "needs_attention", "cancelled", "skipped"].includes(selectedReport.status) ? <button type="button" onClick={() => void archiveReport(selectedReport.id)}>{t.archiveReport}</button> : null}</div></header><p>{formatDate(selectedReport.completed_at || selectedReport.created_at, activeLang)}</p><dl className="bi-version-vector">{(selectedReport.version_vector || []).map((entry) => <div key={entry.widget_id}><dt>{entry.widget_id}</dt><dd>v{entry.version_number} · {entry.dataset_version_id} · {entry.content_hash || t.noHash}</dd></div>)}</dl>{(selectedReport.result_snapshot?.widgets || []).map((item) => <section className="bi-report-widget" key={item.widget_id}><h4>{item.title}</h4><p>{t.statusLabel}: {item.status}</p>{item.result?.kpis?.map((kpi, index) => <p key={`${kpi.label}-${index}`}><strong>{kpi.label}:</strong> {kpi.display_value ?? String(kpi.value ?? "—")}</p>)}<ResultTable rows={item.result?.tables?.[0]?.rows || []} /></section>)}{selectedReport.warnings?.length ? <ul>{selectedReport.warnings.map((warning, index) => <li key={`${warning.code}-${index}`}>{warning.code}</li>)}</ul> : null}</article>{selectedReport.access?.is_owner && deliveryAvailable ? <section className="bi-delivery-history" aria-labelledby="bi-delivery-history-title"><h3 id="bi-delivery-history-title">{t.deliveryHistory}</h3>{deliveryHistory.length ? <ul className="bi-report-list">{deliveryHistory.map((item) => <li key={item.id}><div><strong>{item.recipient?.email || item.recipient_user_id}</strong><small>{item.channel} · {item.status}</small><small>{t.attempts}: {item.attempts}/{item.max_attempts}{item.last_error_code ? ` · ${item.last_error_code}` : ""}</small></div></li>)}</ul> : <p className="bi-empty-inline">{t.noDeliveries}</p>}</section> : null}{selectedReport.access?.is_owner ? (sharingAvailable ? <SharingPanel copy={t} members={reportMembers} shares={reportShares} selectedMemberId={reportShareMember} permission="viewer" viewerOnly onMemberChange={setReportShareMember} onPermissionChange={() => {}} onShare={() => void shareReport()} onRevoke={(share) => void revokeReportShare(share)} /> : <aside className="bi-notice is-warning"><AlertTriangle size={20} aria-hidden="true" /><div><strong>{t.sharingUnavailable}</strong></div></aside>) : null}</> : null}
              </>}
            </section>
          )}
        </>
      )}
    </main>
  );
}
