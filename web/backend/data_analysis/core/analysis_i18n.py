from __future__ import annotations

from copy import deepcopy
from typing import Any
import re


RTL_LANGUAGES = {"ar", "he", "fa", "ur"}

DEFAULT_SYMBOLS = {
    "currency": "",
    "percent": "%",
    "decimal_separator": ".",
    "thousands_separator": ",",
}

TRANSLATIONS = {
    "ar": {
        "Finance": "المالية",
        "Operations": "العمليات",
        "Program monitoring": "متابعة البرامج",
        "Forms": "النماذج",
        "Assisted": "المساعد",
        "Assisted analysis": "التحليل المساعد",
        "Offline question": "سؤال محلي",
        "Custom metric": "مؤشر مخصص",
        "Profit and loss summary": "ملخص الربح والخسارة",
        "Rows with calculated profit": "صفوف مع الربح المحسوب",
        "Budget vs actual": "الميزانية مقابل الفعلي",
        "Expense summary": "ملخص المصروفات",
        "Revenue by group": "الإيرادات حسب المجموعة",
        "Monthly summary": "ملخص شهري",
        "Daily summary": "ملخص يومي",
        "Cash flow summary": "ملخص التدفق النقدي",
        "Top expenses": "أعلى المصروفات",
        "Financial ratios": "النسب المالية",
        "Negative value check": "فحص القيم السالبة",
        "Transaction summary": "ملخص المعاملات",
        "Cost per beneficiary": "التكلفة لكل مستفيد",
        "Donor funding summary": "ملخص تمويل الجهات المانحة",
        "Department summary": "ملخص الأقسام",
        "Top items": "أعلى العناصر",
        "Average price by department": "متوسط السعر حسب القسم",
        "Item counts": "عدد العناصر",
        "Revenue by item": "الإيرادات حسب العنصر",
        "Quantity by department": "الكمية حسب القسم",
        "Indicator progress": "تقدم المؤشرات",
        "Target achievement": "تحقيق الهدف",
        "Beneficiary summary": "ملخص المستفيدين",
        "Disaggregation summary": "ملخص التصنيف التفصيلي",
        "Baseline to endline change": "التغير من خط الأساس إلى النهاية",
        "Activity completion rate": "معدل إنجاز الأنشطة",
        "Survey question summary": "ملخص أسئلة الاستبيان",
        "Location summary": "ملخص المواقع",
        "Partner summary": "ملخص الشركاء",
        "Vulnerability summary": "ملخص الهشاشة",
        "Complaint and feedback summary": "ملخص الشكاوى والتغذية الراجعة",
        "Case status summary": "ملخص حالة الحالات",
        "Attendance rate": "معدل الحضور",
        "Form response overview": "نظرة عامة على ردود النموذج",
        "Question distribution": "توزيع الإجابات",
        "Numeric question summary": "ملخص الأسئلة الرقمية",
        "Rating summary": "ملخص التقييمات",
        "Multi-select summary": "ملخص الاختيارات المتعددة",
        "Column suggestions": "اقتراحات الأعمدة",
        "Total revenue": "إجمالي الإيرادات",
        "Total cost": "إجمالي التكلفة",
        "Total profit": "إجمالي الربح",
        "Profit margin": "هامش الربح",
        "Total budget": "إجمالي الميزانية",
        "Total actual": "إجمالي الفعلي",
        "Variance": "الفرق",
        "Burn rate": "معدل الصرف",
        "Total expense": "إجمالي المصروفات",
        "Average expense": "متوسط المصروفات",
        "Max expense": "أعلى مصروف",
        "Min expense": "أقل مصروف",
        "Total inflow": "إجمالي الداخل",
        "Total outflow": "إجمالي الخارج",
        "Net cash flow": "صافي التدفق النقدي",
        "Gross profit": "إجمالي الربح",
        "Gross margin": "هامش الربح الإجمالي",
        "Cost to revenue": "التكلفة إلى الإيرادات",
        "Net profit": "صافي الربح",
        "Net margin": "هامش صافي الربح",
        "Total amount": "إجمالي المبلغ",
        "Average amount": "متوسط المبلغ",
        "Median amount": "وسيط المبلغ",
        "Rows": "الصفوف",
        "Unique transactions": "المعاملات الفريدة",
        "Total quantity": "إجمالي الكمية",
        "Actual": "الفعلي",
        "Target": "الهدف",
        "Gap": "الفجوة",
        "Achievement": "نسبة الإنجاز",
        "Total beneficiaries": "إجمالي المستفيدين",
        "Responses": "الردود",
        "Questions / columns": "الأسئلة / الأعمدة",
        "Completion rate": "معدل الاكتمال",
        "Missing answers": "الإجابات المفقودة",
        "Average rating": "متوسط التقييم",
        "Median rating": "وسيط التقييم",
    }
}

REPORT_TITLES = {
    "profit_loss_summary": "Profit and loss summary",
    "add_profit_column": "Rows with calculated profit",
    "budget_vs_actual": "Budget vs actual",
    "expense_summary": "Expense summary",
    "revenue_by_group": "Revenue by group",
    "monthly_summary": "Monthly summary",
    "daily_summary": "Daily summary",
    "cash_flow_summary": "Cash flow summary",
    "top_expenses": "Top expenses",
    "financial_ratios": "Financial ratios",
    "detect_negative_values": "Negative value check",
    "transaction_summary": "Transaction summary",
    "cost_per_beneficiary": "Cost per beneficiary",
    "donor_funding_summary": "Donor funding summary",
    "department_summary": "Department summary",
    "top_meals": "Top items",
    "average_price_by_department": "Average price by department",
    "meal_counts": "Item counts",
    "revenue_by_meal": "Revenue by item",
    "quantity_by_department": "Quantity by department",
    "indicator_progress": "Indicator progress",
    "target_achievement": "Target achievement",
    "beneficiary_summary": "Beneficiary summary",
    "disaggregation_summary": "Disaggregation summary",
    "baseline_endline_change": "Baseline to endline change",
    "activity_completion_rate": "Activity completion rate",
    "survey_question_summary": "Survey question summary",
    "location_summary": "Location summary",
    "partner_summary": "Partner summary",
    "vulnerability_summary": "Vulnerability summary",
    "complaint_feedback_summary": "Complaint and feedback summary",
    "case_status_summary": "Case status summary",
    "attendance_rate": "Attendance rate",
    "response_overview": "Form response overview",
    "question_distribution": "Question distribution",
    "numeric_question_summary": "Numeric question summary",
    "rating_summary": "Rating summary",
    "multi_select_summary": "Multi-select summary",
    "column_suggestions": "Column suggestions",
    "offline_question": "Assisted analysis",
    "custom_metric": "Custom metric",
}


def normalize_language(language: str | None) -> str:
    value = (language or "en").lower().strip()
    if value.startswith("ar"):
        return "ar"
    return "en"


def direction_for(language: str | None) -> str:
    return "rtl" if normalize_language(language) in RTL_LANGUAGES else "ltr"


def normalize_symbols(symbols: dict[str, Any] | None = None) -> dict[str, str]:
    merged = {**DEFAULT_SYMBOLS, **(symbols or {})}
    return {key: str(value) for key, value in merged.items()}


def translate(text: str, language: str | None = "en") -> str:
    lang = normalize_language(language)
    return TRANSLATIONS.get(lang, {}).get(text, text)


def report_title(report_id: str, fallback: str, language: str | None = "en") -> str:
    return translate(REPORT_TITLES.get(report_id, fallback), language)


def localized_catalog(catalog: dict[str, Any], language: str | None = "en") -> dict[str, Any]:
    localized = deepcopy(catalog)
    for _domain, domain_config in localized.items():
        domain_config["label"] = translate(domain_config.get("label", ""), language)
        for report in domain_config.get("reports", []):
            report["label"] = translate(report.get("label", ""), language)
    return localized


def has_arabic(value: str | None) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", str(value or "")))
