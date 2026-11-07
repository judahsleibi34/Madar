from tests.account_work_test_support import account_fixture
import tempfile
import unittest
from pathlib import Path
from unittest.mock import ANY, patch

from openpyxl import load_workbook

from data_analysis.routes import data_routes
from services import bi_report_export_service, bi_reporting_service


PROJECT = "11111111-1111-4111-8111-111111111111"
DATASET = "22222222-2222-4222-8222-222222222222"
VERSION = "33333333-3333-4333-8333-333333333333"
WIDGET = "44444444-4444-4444-8444-444444444444"
RUN = "55555555-5555-4555-8555-555555555555"


def immutable_report():
    vector = [{
        "widget_id": WIDGET, "dataset_id": DATASET, "dataset_version_id": VERSION,
        "version_number": 4, "content_hash": "a" * 64, "version_policy": "pinned",
    }]
    return {
        "id": RUN, "creator_user_id": 7, "status": "completed", "completed_at": "2026-10-26T12:00:00Z",
        "definition_snapshot": {"dashboard": {"name": "=Unsafe dashboard"}},
        "version_vector": vector,
        "warnings": [{"code": "partial_period", "widget_id": WIDGET}],
        "result_snapshot": {
            "title": "تقرير العمليات", "generated_at": "2026-10-26T12:00:00Z",
            "version_vector": vector,
            "widgets": [{
                "widget_id": WIDGET, "title": "=إجمالي العمليات", "status": "ready",
                "provenance": {
                    **vector[0], "project_id": PROJECT, "operation": "sum",
                },
                "result": {
                    "summary": "ملخص ثابت",
                    "kpis": [{"label": "+الإجمالي", "value": 30, "display_value": "30"}],
                    "tables": [{"title": "الجدول", "rows": [
                        {"المنطقة": "الشمال", "القيمة": 20},
                        {"المنطقة": "=CMD", "القيمة": 10},
                    ]}],
                    "charts": [{"title": "حسب المنطقة", "type": "bar", "x": "المنطقة", "y": "القيمة",
                                "data": [{"المنطقة": "الشمال", "القيمة": 20}, {"المنطقة": "الجنوب", "القيمة": 10}]}],
                },
            }],
        },
    }


class BiReportExportServiceTests(unittest.TestCase):
    def setUp(self):
        self.fence_client = self.enterContext(account_fixture([(3, 7)]))

    def test_arabic_pdf_is_private_bounded_and_uses_immutable_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path, filename, media_type = bi_report_export_service.write_export(
                report=immutable_report(), tenant_id=3, root=Path(directory),
                export_format="pdf", language="ar",
            )
            payload = path.read_bytes()
            self.assertTrue(payload.startswith(b"%PDF-"))
            self.assertLess(len(payload), bi_report_export_service.MAX_EXPORT_BYTES)
            self.assertEqual(media_type, "application/pdf")
            self.assertTrue(filename.endswith(".pdf"))
            self.assertEqual(path.parents[1].name, RUN)
            self.assertIn("reports/tenant_3", path.as_posix())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_xlsx_has_summary_results_provenance_warnings_rtl_and_no_formulas(self):
        with tempfile.TemporaryDirectory() as directory:
            path, filename, media_type = bi_report_export_service.write_export(
                report=immutable_report(), tenant_id=3, root=Path(directory),
                export_format="xlsx", language="ar",
            )
            workbook = load_workbook(path, data_only=False)
            self.assertEqual(media_type, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.assertTrue(filename.endswith(".xlsx"))
            self.assertEqual(len(workbook.sheetnames), 4)
            self.assertTrue(all(workbook[name].sheet_view.rightToLeft for name in workbook.sheetnames))
            values = [cell.value for sheet in workbook.worksheets for row in sheet.iter_rows() for cell in row]
            self.assertIn(VERSION, values)
            self.assertIn("partial_period", values)
            self.assertIn("'=إجمالي العمليات", values)
            self.assertIn("'+الإجمالي", values)
            self.assertIn("'=CMD", values)
            self.assertFalse(any(cell.data_type == "f" for sheet in workbook.worksheets
                                 for row in sheet.iter_rows() for cell in row))

    def test_snapshot_provenance_mismatch_and_row_overflow_fail_closed(self):
        mismatch = immutable_report()
        mismatch["result_snapshot"]["widgets"][0]["provenance"]["dataset_version_id"] = PROJECT
        with self.assertRaisesRegex(bi_report_export_service.ReportExportError, "provenance_mismatch"):
            bi_report_export_service.validated_report(mismatch)

        oversized = immutable_report()
        oversized["result_snapshot"]["widgets"][0]["result"]["tables"][0]["rows"] = [
            {"value": index} for index in range(bi_report_export_service.MAX_EXPORT_ROWS + 1)
        ]
        with self.assertRaisesRegex(bi_report_export_service.ReportExportError, "row_limit"):
            bi_report_export_service.validated_report(oversized)

    @patch.object(bi_reporting_service, "get_private_charts_dir", return_value=Path("/private/reports"))
    @patch.object(bi_reporting_service.bi_report_export_service, "write_export",
                  return_value=(Path("/private/reports/report.pdf"), "report.pdf", "application/pdf"))
    @patch.object(bi_reporting_service, "get_report", return_value=immutable_report())
    def test_authorized_export_preserves_exact_scope(self, get_report, write_export, _private_root):
        result = bi_reporting_service.report_export_artifact(
            tenant_id=3, project_id=PROJECT, user_id=7, report_id=RUN,
            export_format="pdf", language="en", client=object(),
        )
        self.assertEqual(result[1], "report.pdf")
        get_report.assert_called_once_with(
            tenant_id=3, project_id=PROJECT, user_id=7, report_id=RUN, client=ANY,
        )
        self.assertEqual(write_export.call_args.kwargs["report"]["version_vector"][0]["dataset_version_id"], VERSION)

    def test_pdf_and_xlsx_routes_forward_authenticated_scope_and_stay_private(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / "report.pdf"; pdf.write_bytes(b"%PDF-test")
            xlsx = root / "report.xlsx"; xlsx.write_bytes(b"PK-test")
            with patch.object(data_routes, "get_storage_scope", return_value=("3", "7")), \
                 patch.object(data_routes, "enforce_data_workspace_rate_limit") as rate_limit, \
                 patch.object(data_routes.bi_reporting_service, "report_export_artifact",
                              side_effect=[(pdf, "report.pdf", "application/pdf"),
                                           (xlsx, "report.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")]) as export:
                pdf_response = data_routes.download_bi_report_pdf(
                    user_id=7, project_id=PROJECT, report_id=RUN,
                    request=object(), response=object(), language="ar",
                )
                xlsx_response = data_routes.download_bi_report_xlsx(
                    user_id=7, project_id=PROJECT, report_id=RUN,
                    request=object(), response=object(), language="en",
                )
            self.assertEqual(pdf_response.media_type, "application/pdf")
            self.assertEqual(xlsx_response.media_type, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            self.assertEqual(pdf_response.headers["cache-control"], "private, no-store")
            self.assertEqual(xlsx_response.headers["x-content-type-options"], "nosniff")
            self.assertEqual(export.call_args_list[0].kwargs, {
                "tenant_id": 3, "project_id": PROJECT, "user_id": 7, "report_id": RUN,
                "export_format": "pdf", "language": "ar", "request": ANY,
            })
            self.assertEqual(export.call_args_list[1].kwargs["export_format"], "xlsx")
            self.assertEqual(rate_limit.call_count, 2)


if __name__ == "__main__":
    unittest.main()
