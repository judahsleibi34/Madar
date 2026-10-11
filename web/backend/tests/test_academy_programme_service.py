"""Report exports must remain safe when user-controlled cells reach spreadsheets."""
import csv
import io
import unittest
from services.academy_programme_service import csv_export


class AcademyProgrammeExportTests(unittest.TestCase):
    def test_formula_prefixes_and_multiline_data_are_escaped_without_losing_columns(self):
        result={'enrollments':[{'course_name':'\t=HYPERLINK("https://example.com")','name':'@SUM(1,2)','email':'person@example.com','progress_percent':70,'enrolled_at':'2026-10-11'}, {'course_name':'Ordinary course','name':'Line one\nLine two','progress_percent':0}]}
        rows=list(csv.DictReader(io.StringIO(csv_export(result))))
        self.assertEqual(rows[0]['course_name'],"'\t=HYPERLINK(\"https://example.com\")")
        self.assertEqual(rows[0]['name'],"'@SUM(1,2)")
        self.assertEqual(rows[0]['progress_percent'],'70')
        self.assertEqual(rows[1]['name'],'Line one\nLine two')
        self.assertEqual(rows[1]['course_name'],'Ordinary course')
