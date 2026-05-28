import { useEffect, useMemo, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "/api";

const analysisUiText = {
  en: {
    kicker: "Data workspace",
    title: "Analyze collected data",
    subtitle: "Import form responses or upload a spreadsheet, review the data, clean it, and run an analysis.",
    working: "Working...",
    run: "Run analysis",
    sourceLabel: "Choose data source",
    websiteData: "Website form data",
    spreadsheetUpload: "Spreadsheet upload",
    externalLink: "External link / API",
    fromWebsite: "From your website",
    useResponses: "Use collected form responses",
    responsesDescription: "Turn submitted website forms into a dataset for analysis.",
    form: "Form",
    responses: "responses",
    importResponses: "Import responses",
    viewResponses: "View responses",
    fromFile: "From a file",
    uploadSpreadsheet: "Upload a spreadsheet",
    fileSupport: "CSV, XLS, and XLSX files are supported.",
    chooseFile: "Choose file or drop it here",
    readyToLoad: "Ready to load",
    spreadsheetHint: "Use a spreadsheet exported from your tools",
    loadFile: "Load file",
    fromSystem: "From another system",
    connectLink: "Connect a public data link",
    linkDescription: "Use CSV, Excel, JSON API, or a published Google Sheet.",
    dataLink: "Data link",
    sheetsNote: "Google Sheets must be shared publicly or published to the web.",
    loadLink: "Load link",
    preview: "Preview",
    noData: "No data loaded",
    chooseData: "Choose form responses or upload a spreadsheet.",
    readyRows: (rows, columns) => `${rows} rows and ${columns} columns are ready.`,
  },
  ar: {
    kicker: "مساحة البيانات",
    title: "تحليل البيانات المجمعة",
    subtitle: "استورد ردود النماذج أو ارفع جدولا، ثم راجع البيانات ونظفها وحللها.",
    working: "جارٍ العمل...",
    run: "تشغيل التحليل",
    sourceLabel: "اختر مصدر البيانات",
    websiteData: "بيانات نماذج الموقع",
    spreadsheetUpload: "رفع جدول",
    externalLink: "رابط خارجي / API",
    fromWebsite: "من موقعك",
    useResponses: "استخدم ردود النماذج",
    responsesDescription: "حول ردود الموقع إلى مجموعة بيانات للتحليل.",
    form: "النموذج",
    responses: "ردود",
    importResponses: "استيراد الردود",
    viewResponses: "عرض الردود",
    fromFile: "من ملف",
    uploadSpreadsheet: "رفع جدول",
    fileSupport: "يتم دعم ملفات CSV و XLS و XLSX.",
    chooseFile: "اختر ملفا أو أسقطه هنا",
    readyToLoad: "جاهز للتحميل",
    spreadsheetHint: "استخدم جدولا مصدرا من أدواتك",
    loadFile: "تحميل الملف",
    fromSystem: "من نظام آخر",
    connectLink: "ربط مصدر بيانات عام",
    linkDescription: "استخدم CSV أو Excel أو JSON API أو Google Sheet منشور.",
    dataLink: "رابط البيانات",
    sheetsNote: "يجب أن تكون Google Sheets مشاركة عاما أو منشورة.",
    loadLink: "تحميل الرابط",
    preview: "معاينة",
    noData: "لا توجد بيانات",
    chooseData: "اختر ردود نموذج أو ارفع جدولا.",
    readyRows: (rows, columns) => `${rows} صفوف و ${columns} أعمدة جاهزة.`,
  },
};

const dataWorkbenchText = {
  en: {
    kicker: "Data workspace",
    title: "Report builder",
    subtitle: "Load data, prepare it, map the fields, and generate one focused report from your workspace.",
    working: "Working...",
    run: "Generate report",
    sourceLabel: "Choose data source",
    websiteData: "Website form data",
    spreadsheetUpload: "Spreadsheet upload",
    externalLink: "External link / API",
    fromWebsite: "From your website",
    useResponses: "Use collected form responses",
    responsesDescription: "Turn submitted website forms into a dataset for reporting.",
    form: "Form",
    responses: "responses",
    importResponses: "Import responses",
    viewResponses: "View responses",
    fromFile: "From a file",
    uploadSpreadsheet: "Upload a spreadsheet",
    fileSupport: "CSV, XLS, and XLSX files are supported.",
    chooseFile: "Choose file or drop it here",
    readyToLoad: "Ready to load",
    spreadsheetHint: "Use a spreadsheet exported from your tools",
    loadFile: "Load file",
    fromSystem: "From another system",
    connectLink: "Connect a public data link",
    linkDescription: "Use CSV, Excel, JSON API, or a published Google Sheet.",
    dataLink: "Data link",
    sheetsNote: "Google Sheets must be shared publicly or published to the web.",
    loadLink: "Load link",
    preview: "Preview",
    report: "Report",
    reportCanvas: "Report canvas",
    dataSource: "Data source",
    review: "Review",
    prepare: "Prepare",
    analyze: "Analyze",
    understandData: "Understand the data",
    cleanData: "Clean the data",
    cleanDataDescription: "Apply data fixes before generating the report.",
    chooseReport: "Choose report type",
    chooseReportDescription: "Select the report category, report, and field mapping.",
    reportType: "Report",
    reportReady: "Report generated.",
    reportWaiting: "Generate a report to display results here.",
    inspectionWaiting: "Choose a review action to display results here.",
    datasetPreview: "Dataset preview",
    dataOverview: "Data overview",
    columnStatistics: "Column statistics",
    missingValues: "Missing values",
    dataQuality: "Data quality",
    statistics: "Statistics",
    overview: "Overview",
    quality: "Quality",
    noResult: "No result yet",
    noResultDescription: "Choose a data source and generate a report.",
    noDatasetLoaded: "No dataset loaded",
    noDatasetDescription: "Import submitted form responses or upload a spreadsheet to begin.",
    noColumns: "No columns found",
    noColumnsDescription: "The dataset loaded, but no columns were detected.",
    noRows: "No matching rows",
    noRowsDescription: "Try a different search term.",
    columnsDetected: (count) => `${count} columns detected`,
    columnsHint: "Use column visibility to focus on the fields you need.",
    numericColumns: (count) => `${count} numeric`,
    moreColumns: (count) => `+${count} more`,
    searchRows: "Search preview rows...",
    rows: "Rows",
    columns: "Columns",
    visibleColumns: "Visible columns",
    firstColumns: "First 8",
    allColumns: "All",
    showingRows: (start, end, total, datasetTotal) =>
      `Showing ${start}-${end} of ${total} preview rows${datasetTotal ? ` - ${datasetTotal} total rows in dataset` : ""}`,
    visibleColumnsCount: (visible, total) => `${visible} of ${total} columns visible`,
    first: "First",
    previous: "Previous",
    next: "Next",
    last: "Last",
    pageOf: (page, total) => `Page ${page} of ${total}`,
    yes: "Yes",
    no: "No",
    noGrouping: "No grouping",
    selectColumn: "Select column",
    loadDataToChooseColumns: "Load data to choose columns.",
    trimText: "Clean spaces in text columns",
    lowercaseText: "Standardize text to lowercase",
    removeDuplicates: "Remove duplicate rows",
    removeMissingRows: "Remove rows with empty answers",
    fillMissing: "Fill missing values",
    fillColumn: "Column to fill",
    fillWith: "Fill with",
    mostCommonValue: "Most common value",
    average: "Average",
    median: "Median",
    previousValue: "Previous value",
    nextValue: "Next value",
    customValue: "Custom value",
    convertColumn: "Convert column",
    convertTo: "Convert to",
    number: "Number",
    date: "Date",
    text: "Text",
    category: "Category",
    yesNo: "Yes / no",
    renameColumn: "Rename column",
    newName: "New name",
    removeOutliersFrom: "Remove outliers from",
    excludeColumns: "Exclude columns",
    noData: "No data loaded",
    chooseData: "Choose form responses or upload a spreadsheet.",
    readyRows: (rows, columns) => `${rows} rows and ${columns} columns are ready.`,
    googleSheetsDataset: "Google Sheets dataset",
    externalDataset: "External dataset",
    chooseFileFirst: "Choose a file first.",
    loadDataBeforeReview: "Load data before reviewing it.",
    loadDataBeforeAnalysis: "Load data before generating a report.",
    pasteLinkFirst: "Paste a public data link or API URL first.",
    createFormFirst: "Create a form before importing collected data.",
    emptyForm: "This form has no submitted responses yet.",
  },
  ar: {
    kicker: "مساحة البيانات",
    title: "منشئ التقارير",
    subtitle: "حمّل البيانات، جهزها، اربط الحقول، ثم أنشئ تقريرا واحدا واضحا من مساحة العمل.",
    working: "جار العمل...",
    run: "إنشاء التقرير",
    sourceLabel: "اختر مصدر البيانات",
    websiteData: "بيانات نماذج الموقع",
    spreadsheetUpload: "رفع جدول بيانات",
    externalLink: "رابط خارجي / API",
    fromWebsite: "من موقعك",
    useResponses: "استخدم ردود النماذج",
    responsesDescription: "حوّل ردود نماذج الموقع إلى مجموعة بيانات جاهزة للتقارير.",
    form: "النموذج",
    responses: "ردود",
    importResponses: "استيراد الردود",
    viewResponses: "عرض الردود",
    fromFile: "من ملف",
    uploadSpreadsheet: "رفع جدول بيانات",
    fileSupport: "يدعم ملفات CSV و XLS و XLSX.",
    chooseFile: "اختر ملفا أو اسحبه هنا",
    readyToLoad: "جاهز للتحميل",
    spreadsheetHint: "استخدم جدول بيانات مصدره أدواتك",
    loadFile: "تحميل الملف",
    fromSystem: "من نظام آخر",
    connectLink: "ربط مصدر بيانات عام",
    linkDescription: "استخدم CSV أو Excel أو JSON API أو Google Sheet منشورا.",
    dataLink: "رابط البيانات",
    sheetsNote: "يجب أن يكون Google Sheet مشتركا للعامة أو منشورا على الويب.",
    loadLink: "تحميل الرابط",
    preview: "معاينة",
    report: "التقرير",
    reportCanvas: "لوحة التقرير",
    dataSource: "مصدر البيانات",
    review: "مراجعة",
    prepare: "تجهيز",
    analyze: "تحليل",
    understandData: "افهم البيانات",
    cleanData: "تنظيف البيانات",
    cleanDataDescription: "طبّق إصلاحات البيانات قبل إنشاء التقرير.",
    chooseReport: "اختر نوع التقرير",
    chooseReportDescription: "حدد التصنيف والتقرير واربط أعمدة البيانات.",
    reportType: "التقرير",
    reportReady: "تم إنشاء التقرير.",
    reportWaiting: "أنشئ التقرير لعرض النتائج هنا.",
    inspectionWaiting: "اختر إجراء مراجعة لعرض النتائج هنا.",
    datasetPreview: "معاينة البيانات",
    dataOverview: "نظرة عامة على البيانات",
    columnStatistics: "إحصاءات الأعمدة",
    missingValues: "القيم المفقودة",
    dataQuality: "جودة البيانات",
    statistics: "الإحصاءات",
    overview: "نظرة عامة",
    quality: "الجودة",
    noResult: "لا توجد نتيجة بعد",
    noResultDescription: "اختر مصدر بيانات وأنشئ تقريرا.",
    noDatasetLoaded: "لم يتم تحميل بيانات",
    noDatasetDescription: "استورد ردود النماذج أو ارفع جدول بيانات للبدء.",
    noColumns: "لم يتم العثور على أعمدة",
    noColumnsDescription: "تم تحميل البيانات، لكن لم يتم اكتشاف أعمدة.",
    noRows: "لا توجد صفوف مطابقة",
    noRowsDescription: "جرب كلمة بحث مختلفة.",
    columnsDetected: (count) => `تم اكتشاف ${count} أعمدة`,
    columnsHint: "استخدم إظهار الأعمدة للتركيز على الحقول المطلوبة.",
    numericColumns: (count) => `${count} رقمية`,
    moreColumns: (count) => `+${count} إضافية`,
    searchRows: "ابحث في صفوف المعاينة...",
    rows: "الصفوف",
    columns: "الأعمدة",
    visibleColumns: "الأعمدة الظاهرة",
    firstColumns: "أول 8",
    allColumns: "الكل",
    showingRows: (start, end, total, datasetTotal) =>
      `عرض ${start}-${end} من ${total} صفوف معاينة${datasetTotal ? ` - ${datasetTotal} صفا في مجموعة البيانات` : ""}`,
    visibleColumnsCount: (visible, total) => `${visible} من ${total} أعمدة ظاهرة`,
    first: "الأول",
    previous: "السابق",
    next: "التالي",
    last: "الأخير",
    pageOf: (page, total) => `الصفحة ${page} من ${total}`,
    yes: "نعم",
    no: "لا",
    noGrouping: "بدون تجميع",
    selectColumn: "اختر عمودا",
    loadDataToChooseColumns: "حمّل البيانات لاختيار الأعمدة.",
    trimText: "تنظيف المسافات في أعمدة النص",
    lowercaseText: "توحيد النص إلى أحرف صغيرة",
    removeDuplicates: "إزالة الصفوف المكررة",
    removeMissingRows: "إزالة الصفوف ذات الإجابات الفارغة",
    fillMissing: "تعبئة القيم المفقودة",
    fillColumn: "العمود المراد تعبئته",
    fillWith: "التعبئة باستخدام",
    mostCommonValue: "القيمة الأكثر تكرارا",
    average: "المتوسط",
    median: "الوسيط",
    previousValue: "القيمة السابقة",
    nextValue: "القيمة التالية",
    customValue: "قيمة مخصصة",
    convertColumn: "تحويل عمود",
    convertTo: "تحويل إلى",
    number: "رقم",
    date: "تاريخ",
    text: "نص",
    category: "تصنيف",
    yesNo: "نعم / لا",
    renameColumn: "إعادة تسمية عمود",
    newName: "الاسم الجديد",
    removeOutliersFrom: "إزالة القيم الشاذة من",
    excludeColumns: "استبعاد أعمدة",
    noData: "لا توجد بيانات",
    chooseData: "اختر ردود نموذج أو ارفع جدول بيانات.",
    readyRows: (rows, columns) => `${rows} صفوف و ${columns} أعمدة جاهزة.`,
    googleSheetsDataset: "بيانات Google Sheets",
    externalDataset: "بيانات خارجية",
    chooseFileFirst: "اختر ملفا أولا.",
    loadDataBeforeReview: "حمّل البيانات قبل مراجعتها.",
    loadDataBeforeAnalysis: "حمّل البيانات قبل إنشاء التقرير.",
    pasteLinkFirst: "الصق رابط بيانات عام أو رابط API أولا.",
    createFormFirst: "أنشئ نموذجا قبل استيراد البيانات المجمعة.",
    emptyForm: "لا توجد ردود مرسلة لهذا النموذج بعد.",
  },
};

const reportGroupText = {
  en: {
    finance: {
      label: "Finance",
      description: "Revenue, cost, budget, donor funding, and transaction reports.",
    },
    meal: {
      label: "Operations",
      description: "Departments, quantities, prices, revenue, and activity summaries.",
    },
    ngo_meal: {
      label: "Program monitoring",
      description: "Progress, beneficiaries, activities, surveys, cases, and feedback.",
    },
  },
  ar: {
    finance: {
      label: "المالية",
      description: "تقارير الإيرادات والتكاليف والميزانيات والتمويل والمعاملات.",
    },
    meal: {
      label: "العمليات",
      description: "ملخصات الأقسام والكميات والأسعار والإيرادات والأنشطة.",
    },
    ngo_meal: {
      label: "متابعة البرامج",
      description: "التقدم والمستفيدون والأنشطة والاستبيانات والحالات والتغذية الراجعة.",
    },
  },
};

const reportMethodText = {
  ar: {
    profit_loss_summary: "ملخص الربح والخسارة",
    add_profit_column: "إضافة عمود الربح",
    budget_vs_actual: "الميزانية مقابل الفعلي",
    expense_summary: "ملخص المصروفات",
    revenue_by_group: "الإيرادات حسب المجموعة",
    monthly_summary: "ملخص شهري",
    daily_summary: "ملخص يومي",
    cash_flow_summary: "ملخص التدفق النقدي",
    top_expenses: "أعلى المصروفات",
    financial_ratios: "النسب المالية",
    detect_negative_values: "فحص القيم السالبة",
    transaction_summary: "ملخص المعاملات",
    cost_per_beneficiary: "التكلفة لكل مستفيد",
    donor_funding_summary: "ملخص تمويل الجهات المانحة",
    department_summary: "ملخص الأقسام",
    top_meals: "أعلى العناصر",
    average_price_by_department: "متوسط السعر حسب القسم",
    meal_counts: "عدد العناصر",
    revenue_by_meal: "الإيرادات حسب العنصر",
    quantity_by_department: "الكمية حسب القسم",
    indicator_progress: "تقدم المؤشرات",
    target_achievement: "تحقيق الأهداف",
    beneficiary_summary: "ملخص المستفيدين",
    disaggregation_summary: "ملخص التصنيفات",
    baseline_endline_change: "التغير بين البداية والنهاية",
    activity_completion_rate: "نسبة إنجاز الأنشطة",
    survey_question_summary: "ملخص أسئلة الاستبيان",
    location_summary: "ملخص المواقع",
    partner_summary: "ملخص الشركاء",
    vulnerability_summary: "ملخص الهشاشة",
    complaint_feedback_summary: "ملخص الشكاوى والملاحظات",
    case_status_summary: "ملخص حالة الحالات",
    attendance_rate: "نسبة الحضور",
  },
};

const fieldLabelText = {
  ar: {
    revenue_column: "عمود الإيرادات",
    cost_column: "عمود التكلفة",
    profit_column: "عمود الربح",
    budget_column: "عمود الميزانية",
    actual_column: "عمود الفعلي",
    group_column: "عمود التجميع",
    expense_column: "عمود المصروفات",
    category_column: "عمود التصنيف",
    date_column: "عمود التاريخ",
    value_columns: "أعمدة القيم",
    inflow_column: "عمود التدفقات الداخلة",
    outflow_column: "عمود التدفقات الخارجة",
    columns: "الأعمدة",
    amount_column: "عمود المبلغ",
    transaction_id_column: "عمود رقم المعاملة",
    beneficiary_column: "عمود المستفيد",
    donor_column: "عمود الجهة المانحة",
    department_column: "عمود القسم",
    numeric_columns: "الأعمدة الرقمية",
    meal_column: "عمود العنصر",
    value_column: "عمود القيمة",
    rows: "عدد الصفوف",
    price_column: "عمود السعر",
    column: "العمود",
    quantity_column: "عمود الكمية",
    indicator_column: "عمود المؤشر",
    target_column: "عمود الهدف",
    group_columns: "أعمدة التجميع",
    disaggregation_columns: "أعمدة التصنيف",
    baseline_column: "عمود خط البداية",
    endline_column: "عمود خط النهاية",
    completed_column: "عمود المنجز",
    planned_column: "عمود المخطط",
    question_column: "عمود السؤال",
    response_column: "عمود الإجابة",
    location_column: "عمود الموقع",
    partner_column: "عمود الشريك",
    vulnerability_column: "عمود الهشاشة",
    channel_column: "عمود القناة",
    status_column: "عمود الحالة",
    attended_column: "عمود الحضور",
    registered_column: "عمود المسجلين",
  },
};

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

const toLabel = (key, lang = "en") =>
  fieldLabelText[lang]?.[key] ||
  String(key)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .replace(/\bNgo\b/g, "NGO");

const getReportMethodLabel = (method, lang = "en") =>
  reportMethodText[lang]?.[method.id] || method.label;

const hasArabic = (value) => /[\u0600-\u06FF]/.test(String(value ?? ""));

const getValueDirection = (value) => (hasArabic(value) ? "rtl" : "ltr");

const displayValue = (value, text = dataWorkbenchText.en) => {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isInteger(value) ? value : Number(value.toFixed(3));
  if (typeof value === "boolean") return value ? text.yes : text.no;
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") return formatJson(value);
  return String(value);
};

const escapeCsvValue = (value) => {
  if (value === null || value === undefined) return '""';

  let text;

  if (Array.isArray(value)) {
    text = value.map((item) => String(item ?? "")).join("; ");
  } else if (value instanceof Date) {
    text = value.toISOString();
  } else if (typeof value === "object") {
    text = JSON.stringify(value);
  } else {
    text = String(value);
  }

  return `"${text.replace(/"/g, '""')}"`;
};

const pickAnalysisPayload = (result, methodLabel) => {
  if (!result || typeof result !== "object") return result;
  if (result.results && typeof result.results === "object") {
    return result.results[methodLabel] ?? Object.values(result.results)[0] ?? result.results;
  }
  return result;
};

const getFriendlyInspectionTitle = (type, text = dataWorkbenchText.en) => {
  if (type === "overview") return text.dataOverview;
  if (type === "statistics") return text.columnStatistics;
  if (type === "missing") return text.missingValues;
  if (type === "quality") return text.dataQuality;
  return text.review;
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

const getDatasetTitle = (dataset, fallback, text = dataWorkbenchText.en) => {
  const name = dataset?.original_filename || fallback;

  if (!name) return fallback;

  if (String(name).startsWith("http")) {
    if (String(name).includes("docs.google.com/spreadsheets")) {
      return text.googleSheetsDataset;
    }

    return text.externalDataset;
  }

  return name;
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

function DatasetSourceText({ value }) {
  if (!value || !String(value).startsWith("http")) return null;

  return (
    <p className="dataset-source-url" title={value}>
      {value}
    </p>
  );
}

function ColumnSummary({ columns = [], numericColumns = [], text = dataWorkbenchText.en }) {
  const visibleColumns = columns.slice(0, 8);
  const hiddenCount = Math.max(0, columns.length - visibleColumns.length);

  if (!columns.length) return null;

  return (
    <div className="column-summary">
      <div className="column-summary-header">
        <div>
          <strong>{text.columnsDetected(columns.length)}</strong>
          <p>{text.columnsHint}</p>
        </div>

        <span>{text.numericColumns(numericColumns.length)}</span>
      </div>

      <div className="column-summary-list">
        {visibleColumns.map((column) => (
          <span
            key={column}
            className={numericColumns.includes(column) ? "numeric" : ""}
            title={column}
            dir={getValueDirection(column)}
          >
            {column}
          </span>
        ))}

        {hiddenCount > 0 && (
          <span className="more-columns">
            {text.moreColumns(hiddenCount)}
          </span>
        )}
      </div>
    </div>
  );
}

function DataPreviewGrid({
  columns = [],
  rows = [],
  totalRows,
  pageSizeOptions = [10, 25, 50],
  text = dataWorkbenchText.en,
}) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(pageSizeOptions[0]);
  const [search, setSearch] = useState("");
  const [visibleColumns, setVisibleColumns] = useState(columns);

  useEffect(() => {
    setVisibleColumns(columns);
    setPage(1);
    setSearch("");
  }, [columns]);

  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase();

    if (!query) return rows;

    return rows.filter((row) =>
      columns.some((column) =>
        String(row[column] ?? "").toLowerCase().includes(query)
      )
    );
  }, [rows, columns, search]);

  const filteredTotal = filteredRows.length;
  const totalPages = Math.max(1, Math.ceil(filteredTotal / pageSize));
  const safePage = Math.min(page, totalPages);

  const visibleRows = useMemo(() => {
    const start = (safePage - 1) * pageSize;
    return filteredRows.slice(start, start + pageSize);
  }, [filteredRows, safePage, pageSize]);

  const startRow = filteredTotal === 0 ? 0 : (safePage - 1) * pageSize + 1;
  const endRow = Math.min(safePage * pageSize, filteredTotal);

  const toggleColumn = (column) => {
    setVisibleColumns((current) => {
      if (current.includes(column)) {
        if (current.length === 1) return current;
        return current.filter((item) => item !== column);
      }

      return [...current, column];
    });
  };

  const resetColumns = () => setVisibleColumns(columns);

  const showFirstColumns = () => setVisibleColumns(columns.slice(0, 8));

  const goToPage = (nextPage) => {
    setPage(Math.min(Math.max(nextPage, 1), totalPages));
  };

  if (!columns.length) {
    return (
      <div className="analytics-empty compact">
        <strong>{text.noColumns}</strong>
        <p>{text.noColumnsDescription}</p>
      </div>
    );
  }

  return (
    <div className="data-grid-shell">
      <div className="data-grid-toolbar">
        <div className="data-grid-search">
          <input
            type="search"
            value={search}
            placeholder={text.searchRows}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
          />
        </div>

        <div className="data-grid-actions">
          <label>
            {text.rows}
            <select
              value={pageSize}
              onChange={(event) => {
                setPageSize(Number(event.target.value));
                setPage(1);
              }}
            >
              {pageSizeOptions.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>

          <details className="column-menu">
            <summary>{text.columns}</summary>

            <div className="column-menu-panel">
              <div className="column-menu-header">
                <div>
                  <strong>{text.visibleColumns}</strong>
                  <span>{text.visibleColumnsCount(visibleColumns.length, columns.length)}</span>
                </div>

                <div className="column-menu-buttons">
                  <button type="button" onClick={showFirstColumns}>
                    {text.firstColumns}
                  </button>
                  <button type="button" onClick={resetColumns}>
                    {text.allColumns}
                  </button>
                </div>
              </div>

              <div className="column-menu-list">
                {columns.map((column) => (
                  <label key={column} title={column}>
                    <input
                      type="checkbox"
                      checked={visibleColumns.includes(column)}
                      onChange={() => toggleColumn(column)}
                    />
                    <span dir={getValueDirection(column)}>{column}</span>
                  </label>
                ))}
              </div>
            </div>
          </details>
        </div>
      </div>

      <div className="data-grid-meta">
        <span>
          {text.showingRows(startRow, endRow, filteredTotal, typeof totalRows === "number" && totalRows > rows.length ? totalRows : null)}
          {false && typeof totalRows === "number" && totalRows > rows.length
            ? ` · ${totalRows} total rows in dataset`
            : ""}
        </span>

        <span>{text.visibleColumnsCount(visibleColumns.length, columns.length)}</span>
      </div>

      <div className="data-grid-scroll">
        <table className="data-grid-table">
          <thead>
            <tr>
              {visibleColumns.map((column) => (
                <th key={column} title={column} dir={getValueDirection(column)}>
                  {column}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {visibleRows.length > 0 ? (
              visibleRows.map((row, rowIndex) => (
                <tr key={`row_${safePage}_${rowIndex}`}>
                  {visibleColumns.map((column) => {
                    const value = row[column];
                    const formatted = displayValue(value, text);

                    return (
                      <td
                        key={column}
                        title={formatted}
                        dir={getValueDirection(value)}
                      >
                        {formatted}
                      </td>
                    );
                  })}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={visibleColumns.length || 1}>
                  <div className="analytics-empty compact">
                    <strong>{text.noRows}</strong>
                    <p>{text.noRowsDescription}</p>
                  </div>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="data-grid-footer">
        <button type="button" onClick={() => goToPage(1)} disabled={safePage === 1}>
          {text.first}
        </button>

        <button type="button" onClick={() => goToPage(safePage - 1)} disabled={safePage === 1}>
          {text.previous}
        </button>

        <span>
          {text.pageOf(safePage, totalPages)}
        </span>

        <button type="button" onClick={() => goToPage(safePage + 1)} disabled={safePage === totalPages}>
          {text.next}
        </button>

        <button type="button" onClick={() => goToPage(totalPages)} disabled={safePage === totalPages}>
          {text.last}
        </button>
      </div>
    </div>
  );
}

function ResultView({ value, text = dataWorkbenchText.en }) {
  if (!value) {
    return (
      <div className="analytics-empty compact">
        <strong>{text.noResult}</strong>
        <p>{text.noResultDescription}</p>
      </div>
    );
  }

  if (Array.isArray(value) && value.every((item) => item && typeof item === "object" && !Array.isArray(item))) {
    const columns = Array.from(new Set(value.flatMap((row) => Object.keys(row))));

    return (
      <DataPreviewGrid
        columns={columns}
        rows={value}
        totalRows={value.length}
        pageSizeOptions={[5, 10, 25]}
        text={text}
      />
    );
  }

  if (value && typeof value === "object" && !Array.isArray(value)) {
    return (
      <div className="analysis-result-grid">
        {Object.entries(value).map(([key, item]) => (
          <article key={key}>
            <span>{toLabel(key, text === dataWorkbenchText.ar ? "ar" : "en")}</span>
            <strong>{displayValue(item, text)}</strong>
          </article>
        ))}
      </div>
    );
  }

  return <pre className="analysis-json-output friendly">{displayValue(value, text)}</pre>;
}

function ColumnSelect({ label, value, columns, optional, onChange, text = dataWorkbenchText.en }) {
  return (
    <label className="analysis-field">
      <span>{label}</span>
      <select value={value || ""} onChange={(event) => onChange(event.target.value)}>
        <option value="">{optional ? text.noGrouping : text.selectColumn}</option>
        {columns.map((column) => (
          <option key={column} value={column}>
            {column}
          </option>
        ))}
      </select>
    </label>
  );
}

function MultiColumnSelect({ label, value, columns, onChange, text = dataWorkbenchText.en }) {
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
        )) : <em>{text.loadDataToChooseColumns}</em>}
      </div>
    </div>
  );
}

export default function BuilderAnalysisPage({
  lang = "en",
  project,
  getFormFields = () => [],
  selectForm,
  setActiveTab,
}) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const isArabic = activeLang === "ar";
  const t = dataWorkbenchText[activeLang];
  const groupText = reportGroupText[activeLang];
  const availableForms = project?.forms || [];
  const firstFormWithResponses = availableForms.find((form) => form.responses?.length) || availableForms[0];

  const [sourceMode, setSourceMode] = useState("forms");
  const [selectedFormId, setSelectedFormId] = useState(firstFormWithResponses?.id || "");
  const [dataset, setDataset] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [externalUrl, setExternalUrl] = useState("");
  const [inspection, setInspection] = useState(null);
  const [reportMode, setReportMode] = useState("preview");
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
      setAnalysisError(t.chooseFileFirst);
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
      if (!response.ok) throw new Error(data.detail || "The data could not be loaded.");
      setDataset(data);
      setInspection(null);
      setAnalysisResult(null);
      setReportMode("preview");
    } catch (error) {
      setAnalysisError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const loadExternalSource = async () => {
    const inputPath = externalUrl.trim();

    if (!inputPath) {
      setAnalysisError(t.pasteLinkFirst);
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
      if (!response.ok) throw new Error(getFriendlyExternalError(data.detail));

      setDataset({
        ...data,
        file_path: data.file_path || inputPath,
        original_filename: data.original_filename || inputPath,
      });
      setInspection(null);
      setAnalysisResult(null);
      setReportMode("preview");
    } catch (error) {
      setAnalysisError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const importFormResponses = async () => {
    if (!selectedForm) {
      setAnalysisError(t.createFormFirst);
      return;
    }

    if (!selectedForm.responses?.length) {
      setAnalysisError(t.emptyForm);
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
      setAnalysisError(t.loadDataBeforeReview);
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
      if (!response.ok) throw new Error(data.detail || "The review could not be completed.");
      setInspection({ type, data });
      setReportMode("inspection");
    } catch (error) {
      setAnalysisError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const runAnalysis = async () => {
    if (!dataset?.file_path) {
      setAnalysisError(t.loadDataBeforeAnalysis);
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
      setReportMode("analysis");
    } catch (error) {
      setAnalysisError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const renderParamControl = ([key, value]) => {
    const label = toLabel(key, activeLang);
    const optional = key.includes("group") || key.includes("category") || key.includes("expense_column") || key.includes("transaction_id");

    if (Array.isArray(value)) {
      return (
        <MultiColumnSelect
          key={key}
          label={label}
          value={value}
          columns={key.includes("numeric") || key.includes("value") ? numericColumnGuess : columns}
          onChange={(nextValue) => updateParams(key, nextValue)}
          text={t}
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
      const numericHints = ["amount", "cost", "revenue", "actual", "target", "price", "quantity", "budget", "baseline", "endline"];

      return (
        <ColumnSelect
          key={key}
          label={label}
          value={value}
          columns={numericHints.some((hint) => key.includes(hint)) ? numericColumnGuess : columns}
          optional={optional}
          onChange={(nextValue) => updateParams(key, nextValue)}
          text={t}
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
  const reportTitle =
    reportMode === "analysis"
      ? getReportMethodLabel(activeMethod, activeLang)
      : reportMode === "inspection"
        ? getFriendlyInspectionTitle(inspection?.type, t)
        : getDatasetTitle(dataset, t.noData, t);

  const renderReportBody = () => {
    if (reportMode === "analysis") {
      return <ResultView value={analysisPayload} text={t} />;
    }

    if (reportMode === "inspection") {
      return <ResultView value={inspection?.data} text={t} />;
    }

    if (!dataset) {
      return (
        <div className="analytics-empty">
          <strong>{t.noDatasetLoaded}</strong>
          <p>{t.noDatasetDescription}</p>
        </div>
      );
    }

    return (
      <>
        <ColumnSummary columns={columns} numericColumns={numericColumnGuess} text={t} />
        <DataPreviewGrid columns={columns} rows={dataset.preview || []} totalRows={dataset.rows} text={t} />
      </>
    );
  };

  return (
    <div className="workspace-page analytics-dashboard-page analysis-runner-page" dir={isArabic ? "rtl" : "ltr"}>
      <div className="workspace-header analytics-header">
        <div>
          <span className="workspace-kicker">{t.kicker}</span>
          <h2>{t.title}</h2>
          <p>{t.subtitle}</p>
        </div>

        <button type="button" className="primary-action" onClick={runAnalysis} disabled={isLoading || !dataset}>
          {isLoading ? t.working : t.run}
        </button>
      </div>

      {analysisError && <div className="analysis-error">{analysisError}</div>}

      <section className="analysis-source-panel analytics-card">
        <div className="analysis-source-tabs" role="tablist" aria-label={t.sourceLabel}>
          <button type="button" className={sourceMode === "forms" ? "active" : ""} onClick={() => setSourceMode("forms")}>
            {t.websiteData}
          </button>

          <button type="button" className={sourceMode === "upload" ? "active" : ""} onClick={() => setSourceMode("upload")}>
            {t.spreadsheetUpload}
          </button>

          <button type="button" className={sourceMode === "external" ? "active" : ""} onClick={() => setSourceMode("external")}>
            {t.externalLink}
          </button>
        </div>

        {sourceMode === "forms" ? (
          <div className="analysis-source-body">
            <div>
              <span className="workspace-kicker">{t.fromWebsite}</span>
              <h3>{t.useResponses}</h3>
              <p>{t.responsesDescription}</p>
            </div>

            <label className="analysis-field">
              <span>{t.form}</span>
              <select value={selectedForm?.id || ""} onChange={(event) => setSelectedFormId(event.target.value)}>
                {availableForms.map((form) => (
                  <option key={form.id} value={form.id}>
                    {form.title} ({form.responses?.length || 0} {t.responses})
                  </option>
                ))}
              </select>
            </label>

            <div className="analysis-source-actions">
              <button type="button" className="primary-action" onClick={importFormResponses} disabled={isLoading || !selectedForm}>
                {t.importResponses}
              </button>

              <button
                type="button"
                onClick={() => {
                  if (selectedForm) selectForm?.(selectedForm.id);
                  setActiveTab?.("responses");
                }}
              >
                {t.viewResponses}
              </button>
            </div>
          </div>
        ) : sourceMode === "upload" ? (
          <div className="analysis-source-body">
            <div>
              <span className="workspace-kicker">{t.fromFile}</span>
              <h3>{t.uploadSpreadsheet}</h3>
              <p>{t.fileSupport}</p>
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

              <strong>{selectedFile ? selectedFile.name : t.chooseFile}</strong>
              <span>{selectedFile ? t.readyToLoad : t.spreadsheetHint}</span>
            </label>

            <div className="analysis-source-actions">
              <button type="button" className="primary-action" onClick={() => uploadFile(selectedFile)} disabled={isLoading || !selectedFile}>
                {t.loadFile}
              </button>
            </div>
          </div>
        ) : (
          <div className="analysis-source-body">
            <div>
              <span className="workspace-kicker">{t.fromSystem}</span>
              <h3>{t.connectLink}</h3>
              <p>{t.linkDescription}</p>
            </div>

            <label className="analysis-field">
              <span>{t.dataLink}</span>
              <input
                type="url"
                value={externalUrl}
                placeholder="https://example.com/data.csv"
                onChange={(event) => setExternalUrl(event.target.value)}
              />
              <small>{t.sheetsNote}</small>
            </label>

            <div className="analysis-source-actions">
              <button type="button" className="primary-action" onClick={loadExternalSource} disabled={isLoading || !externalUrl.trim()}>
                {t.loadLink}
              </button>
            </div>
          </div>
        )}
      </section>

      <section className="analysis-workbench-layout">
        <aside className="analysis-control-rail analytics-card">
          <section className="analysis-control-section">
            <span className="workspace-kicker">{t.review}</span>
            <h3>{t.understandData}</h3>
            <div className="analysis-action-row">
              <button type="button" onClick={() => runInspection("overview")} disabled={!dataset || isLoading}>{t.overview}</button>
              <button type="button" onClick={() => runInspection("statistics")} disabled={!dataset || isLoading}>{t.statistics}</button>
              <button type="button" onClick={() => runInspection("missing")} disabled={!dataset || isLoading}>{t.missingValues}</button>
              <button type="button" onClick={() => runInspection("quality")} disabled={!dataset || isLoading}>{t.quality}</button>
            </div>
          </section>

          <section className="analysis-control-section">
            <span className="workspace-kicker">{t.prepare}</span>
            <h3>{t.cleanData}</h3>
            <p>{t.cleanDataDescription}</p>

            <div className="analysis-cleaning-grid">
              <label className="analysis-toggle">
                <input type="checkbox" checked={cleaning.trimText} onChange={(event) => updateCleaning("trimText", event.target.checked)} />
                <span>{t.trimText}</span>
              </label>
              <label className="analysis-toggle">
                <input type="checkbox" checked={cleaning.lowercaseText} onChange={(event) => updateCleaning("lowercaseText", event.target.checked)} />
                <span>{t.lowercaseText}</span>
              </label>
              <label className="analysis-toggle">
                <input type="checkbox" checked={cleaning.removeDuplicates} onChange={(event) => updateCleaning("removeDuplicates", event.target.checked)} />
                <span>{t.removeDuplicates}</span>
              </label>
              <label className="analysis-toggle">
                <input type="checkbox" checked={cleaning.removeMissingRows} onChange={(event) => updateCleaning("removeMissingRows", event.target.checked)} />
                <span>{t.removeMissingRows}</span>
              </label>
            </div>

            <div className="analysis-form-grid">
              <label className="analysis-toggle">
                <input type="checkbox" checked={cleaning.fillMissing} onChange={(event) => updateCleaning("fillMissing", event.target.checked)} />
                <span>{t.fillMissing}</span>
              </label>
              <ColumnSelect label={t.fillColumn} value={cleaning.fillColumn} columns={columns} onChange={(value) => updateCleaning("fillColumn", value)} text={t} />
              <label className="analysis-field">
                <span>{t.fillWith}</span>
                <select value={cleaning.fillMethod} onChange={(event) => updateCleaning("fillMethod", event.target.value)}>
                  <option value="mode">{t.mostCommonValue}</option>
                  <option value="mean">{t.average}</option>
                  <option value="median">{t.median}</option>
                  <option value="forward_fill">{t.previousValue}</option>
                  <option value="backward_fill">{t.nextValue}</option>
                  <option value="constant">{t.customValue}</option>
                </select>
              </label>

              {cleaning.fillMethod === "constant" && (
                <label className="analysis-field">
                  <span>{t.customValue}</span>
                  <input type="text" value={cleaning.fillValue} onChange={(event) => updateCleaning("fillValue", event.target.value)} />
                </label>
              )}

              <ColumnSelect label={t.convertColumn} value={cleaning.convertColumn} columns={columns} optional onChange={(value) => updateCleaning("convertColumn", value)} text={t} />
              <label className="analysis-field">
                <span>{t.convertTo}</span>
                <select value={cleaning.convertType} onChange={(event) => updateCleaning("convertType", event.target.value)}>
                  <option value="numeric">{t.number}</option>
                  <option value="datetime">{t.date}</option>
                  <option value="string">{t.text}</option>
                  <option value="category">{t.category}</option>
                  <option value="boolean">{t.yesNo}</option>
                </select>
              </label>
              <ColumnSelect label={t.renameColumn} value={cleaning.renameColumn} columns={columns} optional onChange={(value) => updateCleaning("renameColumn", value)} text={t} />
              <label className="analysis-field">
                <span>{t.newName}</span>
                <input type="text" value={cleaning.renameTo} onChange={(event) => updateCleaning("renameTo", event.target.value)} />
              </label>
              <MultiColumnSelect label={t.removeOutliersFrom} value={cleaning.outlierColumns} columns={numericColumnGuess} text={t} onChange={(value) => {
                updateCleaning("outlierColumns", value);
                updateCleaning("removeOutliers", value.length > 0);
              }} />
              <MultiColumnSelect label={t.excludeColumns} value={cleaning.dropColumns} columns={columns} onChange={(value) => updateCleaning("dropColumns", value)} text={t} />
            </div>
          </section>

          <section className="analysis-control-section">
            <span className="workspace-kicker">{t.analyze}</span>
            <h3>{t.chooseReport}</h3>
            <p>{t.chooseReportDescription}</p>
            <div className="analysis-method-tabs">
              {Object.entries(analysisGroups).map(([key]) => (
                <button key={key} type="button" className={analysisDomain === key ? "active" : ""} onClick={() => setDomain(key)}>
                  <strong>{groupText[key]?.label || analysisGroups[key].label}</strong>
                  <span>{groupText[key]?.description || analysisGroups[key].description}</span>
                </button>
              ))}
            </div>
            <label className="analysis-field">
              <span>{t.reportType}</span>
              <select value={analysisMethod} onChange={(event) => setMethod(event.target.value)}>
                {methods.map((method) => (
                  <option key={method.id} value={method.id}>{getReportMethodLabel(method, activeLang)}</option>
                ))}
              </select>
            </label>
            <div className="analysis-form-grid">
              {Object.entries(activeMethod.template).map(renderParamControl)}
            </div>
          </section>
        </aside>

        <article className="analytics-card analysis-report-canvas">
          <div className="analytics-card-header">
            <div>
              <span className="workspace-kicker">{t.reportCanvas}</span>
              <h3>{reportTitle}</h3>
              {dataset ? (
                <>
                  <p>{reportMode === "analysis" ? t.reportReady : t.readyRows(dataset.rows, dataset.columns.length)}</p>
                  <DatasetSourceText value={dataset.original_filename} />
                </>
              ) : (
                <p>{t.chooseData}</p>
              )}
            </div>
            <button type="button" className="primary-action" onClick={runAnalysis} disabled={isLoading || !dataset}>
              {isLoading ? t.working : t.run}
            </button>
          </div>
          {renderReportBody()}
        </article>
      </section>
    </div>
  );
}
