"""Bounded professional exports for immutable BI report snapshots."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


MAX_EXPORT_BYTES = 5 * 1024 * 1024
MAX_EXPORT_WIDGETS = 24
MAX_EXPORT_ROWS = 500
MAX_EXPORT_COLUMNS = 40
MAX_CELL_CHARACTERS = 4096
MAX_PDF_TABLE_ROWS = 18
MAX_PDF_CHART_POINTS = 30
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")
ILLEGAL_CELL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_PDF_LOCK = threading.Lock()

COPY = {
    "en": {
        "report": "Business Intelligence Report",
        "generated": "Generated",
        "status": "Status",
        "summary": "Summary",
        "widgets": "Widgets",
        "warnings": "Warnings",
        "provenance": "Source and version references",
        "disclosure": "Generic analytical report. Business meaning, units, currencies, and accounting treatment are not inferred.",
        "widget": "Widget",
        "dataset": "Dataset",
        "version": "Version",
        "hash": "Content hash",
        "operation": "Operation",
        "value": "Value",
        "result_type": "Result type",
        "section": "Section",
        "row_field": "Row / field",
        "widget_id": "Widget ID",
        "dataset_version_id": "Dataset version ID",
        "version_policy": "Version policy",
        "code": "Code",
        "no_warnings": "No report warnings.",
        "truncated": "The printable table is truncated; the XLSX export contains the bounded result rows.",
    },
    "ar": {
        "report": "تقرير ذكاء الأعمال",
        "generated": "تاريخ الإنشاء",
        "status": "الحالة",
        "summary": "الملخص",
        "widgets": "الأدوات",
        "warnings": "التحذيرات",
        "provenance": "مراجع المصدر والإصدار",
        "disclosure": "تقرير تحليلي عام. لا يتم استنتاج المعنى التجاري أو الوحدات أو العملات أو المعالجة المحاسبية.",
        "widget": "الأداة",
        "dataset": "مجموعة البيانات",
        "version": "الإصدار",
        "hash": "بصمة المحتوى",
        "operation": "العملية",
        "value": "القيمة",
        "result_type": "نوع النتيجة",
        "section": "القسم",
        "row_field": "الصف / الحقل",
        "widget_id": "معرّف الأداة",
        "dataset_version_id": "معرّف إصدار البيانات",
        "version_policy": "سياسة الإصدار",
        "code": "الرمز",
        "no_warnings": "لا توجد تحذيرات في التقرير.",
        "truncated": "تم اختصار الجدول المطبوع؛ يحتوي ملف XLSX على صفوف النتائج المحدودة.",
    },
}


class ReportExportError(RuntimeError):
    pass


def _text(value: object, *, limit: int = MAX_CELL_CHARACTERS) -> str:
    if value is None:
        return ""
    return ILLEGAL_CELL_CHARACTERS.sub("", str(value))[:limit]


def safe_spreadsheet_cell(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value if math.isfinite(float(value)) else _text(value)
    text = _text(value)
    return f"'{text}" if text.startswith(FORMULA_PREFIXES) else text


def _bounded_rows(rows: object, remaining: int) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or remaining <= 0:
        return []
    bounded: list[dict[str, Any]] = []
    for row in rows[:remaining]:
        if isinstance(row, dict):
            bounded.append(dict(list(row.items())[:MAX_EXPORT_COLUMNS]))
    return bounded


def validated_report(report: dict[str, Any]) -> dict[str, Any]:
    if report.get("status") != "completed":
        raise ReportExportError("report_export_not_ready")
    snapshot = report.get("result_snapshot")
    vector = report.get("version_vector")
    if not isinstance(snapshot, dict) or not isinstance(vector, list):
        raise ReportExportError("report_export_snapshot_invalid")
    widgets = snapshot.get("widgets")
    snapshot_vector = snapshot.get("version_vector")
    if not isinstance(widgets, list) or len(widgets) > MAX_EXPORT_WIDGETS:
        raise ReportExportError("report_export_snapshot_invalid")
    if snapshot_vector != vector:
        raise ReportExportError("report_export_provenance_mismatch")
    by_widget = {str(item.get("widget_id")): item for item in vector if isinstance(item, dict)}
    row_count = 0
    for widget in widgets:
        if not isinstance(widget, dict):
            raise ReportExportError("report_export_snapshot_invalid")
        result = widget.get("result") or {}
        if widget.get("status") == "ready":
            expected = by_widget.get(str(widget.get("widget_id")))
            provenance = widget.get("provenance") or {}
            if not expected or provenance.get("dataset_version_id") != expected.get("dataset_version_id"):
                raise ReportExportError("report_export_provenance_mismatch")
        if isinstance(result, dict):
            for table in (result.get("tables") or []):
                if isinstance(table, dict) and isinstance(table.get("rows"), list):
                    row_count += len(table["rows"])
            for chart in (result.get("charts") or []):
                if isinstance(chart, dict) and isinstance(chart.get("data"), list):
                    row_count += len(chart["data"])
        if row_count > MAX_EXPORT_ROWS:
            raise ReportExportError("report_export_row_limit_exceeded")
    return snapshot


def _report_title(report: dict[str, Any], snapshot: dict[str, Any]) -> str:
    return _text(snapshot.get("title") or (report.get("definition_snapshot") or {}).get("dashboard", {}).get("name") or "Report", limit=160)


def _provenance_rows(report: dict[str, Any], snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    widgets = {str(item.get("widget_id")): item for item in snapshot.get("widgets") or [] if isinstance(item, dict)}
    rows = []
    for entry in report.get("version_vector") or []:
        if not isinstance(entry, dict):
            continue
        widget = widgets.get(str(entry.get("widget_id"))) or {}
        provenance = widget.get("provenance") or {}
        rows.append({
            "widget": widget.get("title") or entry.get("widget_id"),
            "widget_id": entry.get("widget_id"),
            "dataset_id": entry.get("dataset_id"),
            "dataset_version_id": entry.get("dataset_version_id"),
            "version_number": entry.get("version_number"),
            "content_hash": entry.get("content_hash"),
            "version_policy": entry.get("version_policy"),
            "operation": provenance.get("operation"),
        })
    return rows


def _widget_result_rows(snapshot: dict[str, Any]) -> list[list[object]]:
    output: list[list[object]] = []
    for widget in snapshot.get("widgets") or []:
        title = widget.get("title")
        status = widget.get("status")
        result = widget.get("result") or {}
        if not isinstance(result, dict):
            output.append([title, status, "message", "", "", widget.get("reason")])
            continue
        for kpi in (result.get("kpis") or []):
            if isinstance(kpi, dict):
                output.append([title, status, "kpi", kpi.get("label"), "", kpi.get("display_value", kpi.get("value"))])
        for table_index, table in enumerate(result.get("tables") or []):
            if not isinstance(table, dict):
                continue
            rows = _bounded_rows(table.get("rows"), MAX_EXPORT_ROWS - len(output))
            for row_index, row in enumerate(rows, 1):
                for column, value in row.items():
                    output.append([title, status, f"table:{table_index + 1}", table.get("title"), f"{row_index}:{column}", value])
                    if len(output) >= MAX_EXPORT_ROWS:
                        return output
        for chart_index, chart in enumerate(result.get("charts") or []):
            if not isinstance(chart, dict):
                continue
            rows = _bounded_rows(chart.get("data"), MAX_EXPORT_ROWS - len(output))
            for row_index, row in enumerate(rows, 1):
                output.append([title, status, f"chart:{chart_index + 1}", chart.get("title"), row_index,
                               json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)])
                if len(output) >= MAX_EXPORT_ROWS:
                    return output
        if not result.get("kpis") and not result.get("tables") and not result.get("charts"):
            output.append([title, status, "message", "", "", result.get("summary") or widget.get("reason")])
    return output[:MAX_EXPORT_ROWS]


def _style_sheet(sheet, *, rtl: bool, widths: tuple[int, ...]) -> None:
    sheet.sheet_view.rightToLeft = rtl
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="8E2C23")
        cell.alignment = Alignment(horizontal="right" if rtl else "left")
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(index)].width = min(width, 60)
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(horizontal="right" if rtl else "left", vertical="top", wrap_text=True)


def render_xlsx(report: dict[str, Any], destination: Path, *, language: str) -> None:
    snapshot = validated_report(report)
    labels = COPY[language]
    rtl = language == "ar"
    workbook = Workbook()
    summary = workbook.active
    summary.title = labels["summary"]
    title = _report_title(report, snapshot)
    summary_rows = [
        (labels["report"], title),
        (labels["generated"], snapshot.get("generated_at") or report.get("completed_at")),
        (labels["status"], report.get("status")),
        (labels["widgets"], len(snapshot.get("widgets") or [])),
        (labels["warnings"], len(report.get("warnings") or [])),
        ("Disclosure", labels["disclosure"]),
    ]
    summary.append([labels["summary"], labels["value"]])
    for key, value in summary_rows:
        summary.append([safe_spreadsheet_cell(key), safe_spreadsheet_cell(value)])
    _style_sheet(summary, rtl=rtl, widths=(30, 90))

    results = workbook.create_sheet("نتائج الأدوات" if rtl else "Widget Results")
    results.append([labels["widget"], labels["status"], labels["result_type"], labels["section"],
                    labels["row_field"], labels["value"]])
    for row in _widget_result_rows(snapshot):
        results.append([safe_spreadsheet_cell(value) for value in row])
    _style_sheet(results, rtl=rtl, widths=(30, 16, 18, 30, 24, 60))

    provenance = workbook.create_sheet(labels["provenance"][:31])
    provenance.append([labels["widget"], labels["widget_id"], labels["dataset"], labels["dataset_version_id"],
                       labels["version"], labels["hash"], labels["version_policy"], labels["operation"]])
    for row in _provenance_rows(report, snapshot):
        provenance.append([safe_spreadsheet_cell(row[key]) for key in (
            "widget", "widget_id", "dataset_id", "dataset_version_id", "version_number",
            "content_hash", "version_policy", "operation",
        )])
    _style_sheet(provenance, rtl=rtl, widths=(30, 38, 38, 38, 12, 68, 20, 22))

    warnings = workbook.create_sheet(labels["warnings"])
    warnings.append([labels["code"], labels["widget_id"]])
    warning_rows = report.get("warnings") or []
    if warning_rows:
        for warning in warning_rows[:MAX_EXPORT_ROWS]:
            warning = warning if isinstance(warning, dict) else {"code": warning}
            warnings.append([safe_spreadsheet_cell(warning.get("code")), safe_spreadsheet_cell(warning.get("widget_id"))])
    else:
        warnings.append([safe_spreadsheet_cell(labels["no_warnings"]), ""])
    _style_sheet(warnings, rtl=rtl, widths=(45, 38))

    workbook.properties.creator = "Madar"
    workbook.properties.title = title
    workbook.properties.subject = labels["disclosure"]
    workbook.save(destination)


def _pdf_value(value: object, *, limit: int = 220) -> str:
    return _text(value, limit=limit) or "—"


def _pdf_ltr(value: object, *, limit: int = 220) -> str:
    """Keep identifiers/numbers legible when embedded in an Arabic line."""
    return f"\u200e{_pdf_value(value, limit=limit)}\u200e"


def _pdf_timestamp(value: object) -> str:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return _pdf_value(value)
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


def render_pdf(report: dict[str, Any], destination: Path, *, language: str) -> None:
    snapshot = validated_report(report)
    labels = COPY[language]
    rtl = language == "ar"
    from matplotlib import rc_context
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.figure import Figure

    title = _report_title(report, snapshot)
    completed = report.get("completed_at") or snapshot.get("generated_at") or ""
    metadata_date = None
    try:
        metadata_date = datetime.fromisoformat(str(completed).replace("Z", "+00:00"))
    except ValueError:
        pass
    metadata = {"Title": title, "Author": "Madar", "Subject": labels["disclosure"],
                "CreationDate": metadata_date, "ModDate": metadata_date}
    align = "right" if rtl else "left"
    x = .93 if rtl else .07

    def add_text(fig: Figure, y: float, value: object, *, size: float = 10, weight: str = "normal", color: str = "#243745"):
        fig.text(x, y, _pdf_value(value, limit=1000), ha=align, va="top", fontsize=size,
                 fontweight=weight, color=color, wrap=True, parse_math=False)

    with _PDF_LOCK, rc_context({"pdf.fonttype": 42, "font.family": "DejaVu Sans", "text.usetex": False}), \
            PdfPages(destination, metadata=metadata) as pdf:
        cover = Figure(figsize=(8.2677, 11.6929), facecolor="#fffdf8")
        add_text(cover, .93, labels["report"], size=12, weight="bold", color="#8E2C23")
        add_text(cover, .87, title, size=24, weight="bold")
        add_text(cover, .79, f"{labels['generated']}: {_pdf_ltr(_pdf_timestamp(completed)) if rtl else _pdf_timestamp(completed)}", size=10)
        add_text(cover, .75, f"{labels['status']}: {_pdf_ltr(report.get('status')) if rtl else _pdf_value(report.get('status'))}", size=10)
        add_text(cover, .69, labels["disclosure"], size=10, color="#52616b")
        add_text(cover, .61, labels["provenance"], size=14, weight="bold")
        y = .57
        for row in _provenance_rows(report, snapshot)[:MAX_EXPORT_WIDGETS]:
            version = f"v{_pdf_value(row['version_number'])}"
            line = (f"{_pdf_value(row['widget'], limit=70)} | "
                    f"{_pdf_ltr(version) if rtl else version} | "
                    f"{_pdf_ltr(row['dataset_version_id'], limit=40) if rtl else _pdf_value(row['dataset_version_id'], limit=40)} | "
                    f"{_pdf_ltr(row['content_hash'], limit=68) if rtl else _pdf_value(row['content_hash'], limit=68)}")
            add_text(cover, y, line, size=7.5)
            y -= .025
        add_text(cover, max(.14, y - .025), labels["warnings"], size=13, weight="bold")
        warnings = report.get("warnings") or []
        warning_text = "; ".join(_text(item.get("code") if isinstance(item, dict) else item, limit=100) for item in warnings)
        add_text(cover, max(.08, y - .065), warning_text or labels["no_warnings"], size=9, color="#7a4a20")
        pdf.savefig(cover)
        cover.clear()

        for widget in snapshot.get("widgets") or []:
            fig = Figure(figsize=(11.6929, 8.2677), facecolor="white")
            add_text(fig, .94, widget.get("title") or labels["widget"], size=18, weight="bold")
            add_text(fig, .89, f"{labels['status']}: {_pdf_ltr(widget.get('status')) if rtl else _pdf_value(widget.get('status'))}", size=9)
            provenance = widget.get("provenance") or {}
            dataset_id = _pdf_ltr(provenance.get("dataset_id"), limit=45) if rtl else _pdf_value(provenance.get("dataset_id"), limit=45)
            version_id = _pdf_ltr(provenance.get("dataset_version_id"), limit=45) if rtl else _pdf_value(provenance.get("dataset_version_id"), limit=45)
            add_text(fig, .85, f"{labels['dataset']}: {dataset_id}   {labels['version']}: {version_id}", size=8)
            result = widget.get("result") or {}
            if not isinstance(result, dict):
                add_text(fig, .76, widget.get("reason") or "—", size=11)
                pdf.savefig(fig); fig.clear(); continue
            kpis = [item for item in (result.get("kpis") or []) if isinstance(item, dict)][:6]
            if kpis:
                summary = "   |   ".join(
                    f"{_pdf_value(item.get('label'), limit=45)}: "
                    f"{_pdf_ltr(item.get('display_value', item.get('value')), limit=45) if rtl else _pdf_value(item.get('display_value', item.get('value')), limit=45)}"
                    for item in kpis
                )
                add_text(fig, .80, summary, size=11, weight="bold", color="#8E2C23")
            chart = next((item for item in (result.get("charts") or []) if isinstance(item, dict)), None)
            table = next((item for item in (result.get("tables") or []) if isinstance(item, dict)), None)
            chart_bottom = .40 if table else .11
            if chart:
                data = _bounded_rows(chart.get("data"), MAX_PDF_CHART_POINTS)
                x_key, y_key = chart.get("x"), chart.get("y")
                values = []
                labels_values = []
                for row in data:
                    try:
                        number = float(row.get(y_key))
                    except (TypeError, ValueError):
                        continue
                    if math.isfinite(number):
                        values.append(number); labels_values.append(_pdf_value(row.get(x_key), limit=35))
                if values:
                    axis = fig.add_axes([.12, chart_bottom, .78, .33])
                    axis.barh(range(len(values)), values, color="#8E2C23")
                    axis.set_yticks(range(len(values)), labels_values, fontsize=7)
                    axis.invert_yaxis(); axis.grid(axis="x", alpha=.2)
                    axis.set_title(_pdf_value(chart.get("title"), limit=100), fontsize=10, loc="right" if rtl else "left")
            if table:
                rows = _bounded_rows(table.get("rows"), MAX_PDF_TABLE_ROWS)
                columns = list(dict.fromkeys(key for row in rows for key in row))[:8]
                if rows and columns:
                    axis = fig.add_axes([.06, .06, .88, .25 if chart else .58]); axis.axis("off")
                    values = [[_pdf_value(row.get(column), limit=45) for column in columns] for row in rows]
                    table_artist = axis.table(cellText=values, colLabels=[_pdf_value(column, limit=35) for column in columns],
                                              loc="upper center", cellLoc=align, colLoc=align)
                    table_artist.auto_set_font_size(False); table_artist.set_fontsize(6.5); table_artist.scale(1, 1.25)
                    if isinstance(table.get("rows"), list) and len(table["rows"]) > len(rows):
                        fig.text(.5, .025, labels["truncated"], ha="center", fontsize=7, color="#7a4a20")
            if not chart and not table:
                add_text(fig, .70, result.get("summary") or widget.get("reason") or "—", size=11)
            pdf.savefig(fig)
            fig.clear()


def write_export(*, report: dict[str, Any], tenant_id: int, root: Path,
                 export_format: str, language: str) -> tuple[Path, str, str]:
    if export_format not in {"pdf", "xlsx"} or language not in COPY:
        raise ReportExportError("report_export_format_invalid")
    snapshot = validated_report(report)
    private_root = root.resolve()
    temporary_root = private_root / ".report-tmp" / f"tenant_{int(tenant_id)}" / str(report["id"])
    temporary_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(dir=temporary_root, prefix="report-export-",
                                     suffix=f".{export_format}", delete=False) as output:
        temporary = Path(output.name)
    try:
        if export_format == "pdf":
            render_pdf(report, temporary, language=language)
            media_type = "application/pdf"
        else:
            render_xlsx(report, temporary, language=language)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        size = temporary.stat().st_size
        if size <= 0 or size > MAX_EXPORT_BYTES:
            raise ReportExportError("report_export_size_limit_exceeded")
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        snapshot_digest = hashlib.sha256(json.dumps({
            "id": report.get("id"), "result_snapshot": snapshot,
            "version_vector": report.get("version_vector"), "warnings": report.get("warnings"),
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")).hexdigest()
        relative = Path("reports") / f"tenant_{int(tenant_id)}" / str(report["id"]) / "exports" / f"{snapshot_digest}-{language}.{export_format}"
        destination = (private_root / relative).resolve()
        if private_root not in destination.parents:
            raise ReportExportError("report_export_path_invalid")
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
        if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            destination.unlink(missing_ok=True)
            raise ReportExportError("report_export_integrity_failed")
        safe_title = SAFE_FILENAME.sub("-", _report_title(report, snapshot)).strip("-.")[:80] or "report"
        return destination, f"{safe_title}-{str(report['id'])[:8]}.{export_format}", media_type
    finally:
        temporary.unlink(missing_ok=True)
