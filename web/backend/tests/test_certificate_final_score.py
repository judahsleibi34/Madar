import unittest
from unittest.mock import MagicMock, patch

from services.elearning_credentials_service import final_exam_score, with_final_scores


def table_returning(responses):
    """Mock service_supabase whose table(name) chain returns rows per table."""
    db = MagicMock()
    def table(name):
        chain = MagicMock()
        for method in ('select', 'eq', 'in_', 'limit'):
            getattr(chain, method).return_value = chain
        chain.execute.return_value.data = responses[name]
        return chain
    db.table.side_effect = table
    return db


class CertificateFinalScoreTests(unittest.TestCase):
    def test_best_passed_attempt_in_the_certified_section(self):
        db = table_returning({'elearning_credentials': [{'tenant_id': 18, 'completion_id': 'c', 'credential_type': 'cefr_A1'}],
                              'elearning_completion_events': [{'section_id': 's', 'enrollment_id': 'e'}],
                              'elearning_assessment_placements': [{'id': 'p1'}],
                              'elearning_assessment_attempts': [{'score_percentage': 72}, {'score_percentage': 88.5}]})
        with patch('database.service_supabase', db), patch('services.elearning_academy_service.experience_for_tenant', return_value={'lessonComponents': True}):
            self.assertEqual(final_exam_score('MDR-1', 18), 88.5)
        with patch('database.service_supabase', db), patch('services.elearning_academy_service.experience_for_tenant', return_value={}):
            self.assertIsNone(final_exam_score('MDR-1', 18))

    def test_course_certificates_and_failures_have_no_score(self):
        db = table_returning({'elearning_credentials': [{'tenant_id': 18, 'completion_id': 'c', 'credential_type': 'course_completion'}]})
        with patch('database.service_supabase', db):
            self.assertIsNone(final_exam_score('MDR-2', 18))
        broken = MagicMock(); broken.table.side_effect = RuntimeError('down')
        with patch('database.service_supabase', broken):
            self.assertIsNone(final_exam_score('MDR-3'))

    def test_scores_are_added_to_lists_and_single_records(self):
        with patch('services.elearning_credentials_service.final_exam_score', return_value=90.0):
            self.assertEqual(with_final_scores([{'credential_number': 'A'}], 18), [{'credential_number': 'A', 'final_score': 90.0}])
            self.assertEqual(with_final_scores({'credential_number': 'B'}, 18)['final_score'], 90.0)


if __name__ == '__main__':
    unittest.main()
