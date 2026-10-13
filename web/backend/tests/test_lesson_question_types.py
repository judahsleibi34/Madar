import unittest
from unittest.mock import MagicMock, patch

from services.elearning_player_service import with_question_types


class LessonQuestionTypeTests(unittest.TestCase):
    def test_only_question_types_are_added_to_assessment_blocks(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.in_.return_value.is_.return_value.execute.return_value.data = [
            {'assessment_id': 'a1', 'type': 'picture_listen'}, {'assessment_id': 'a1', 'type': 'picture_listen'}, {'assessment_id': 'a2', 'type': 'speaking_practice'}]
        lesson = {'blocks': [{'type': 'text', 'content': {}}, {'type': 'assessment', 'assessment': {'id': 'a1'}}, {'type': 'assessment', 'assessment': {'id': 'a2'}}]}
        with patch('services.elearning_player_service.service_supabase', db):
            result = with_question_types(18, lesson)
        self.assertEqual(result['blocks'][1]['assessment']['question_types'], ['picture_listen'])
        self.assertEqual(result['blocks'][2]['assessment']['question_types'], ['speaking_practice'])
        self.assertNotIn('question_types', result['blocks'][0])
        db.table.assert_called_once_with('elearning_assessment_questions')
        db.table.return_value.select.assert_called_once_with('assessment_id,type')

    def test_lessons_without_assessments_or_failed_lookups_are_unchanged(self):
        self.assertEqual(with_question_types(18, {'blocks': [{'type': 'text'}]}), {'blocks': [{'type': 'text'}]})
        db = MagicMock(); db.table.side_effect = RuntimeError('unavailable')
        lesson = {'blocks': [{'type': 'assessment', 'assessment': {'id': 'a1'}}]}
        with patch('services.elearning_player_service.service_supabase', db):
            self.assertEqual(with_question_types(18, lesson), lesson)


if __name__ == '__main__':
    unittest.main()
