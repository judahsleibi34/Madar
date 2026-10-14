import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from services.elearning_assessments_service import PracticeCheck, check_practice_answer

ACTOR = SimpleNamespace(tenant_id=18, user_id=7)
QUESTION, RIGHT, WRONG = str(uuid4()), str(uuid4()), str(uuid4())


def snapshot(mode='practice', kind='picture_listen'):
    return {'assessment': {'activity_mode': mode}, 'questions': [{'id': QUESTION, 'type': kind, 'config': {
        'options': [{'id': RIGHT}, {'id': WRONG}], 'correct_option_id': RIGHT}}]}


class PracticeAnswerCheckTests(unittest.TestCase):
    def run_check(self, rows, option=RIGHT, question=QUESTION):
        db = MagicMock()
        query = db.table.return_value.select.return_value
        for _ in range(5): query = query.eq.return_value
        query.limit.return_value.execute.return_value.data = rows
        with patch('services.elearning_assessments_service.service_supabase', db):
            result = check_practice_answer(ACTOR, uuid4(), uuid4(), uuid4(), PracticeCheck(question_id=question, option_id=option))
        return result, db

    def test_reports_correct_and_incorrect_choices_in_practice(self):
        self.assertTrue(self.run_check([{'private_snapshot': snapshot()}])[0]['correct'])
        self.assertFalse(self.run_check([{'private_snapshot': snapshot()}], option=WRONG)[0]['correct'])

    def test_only_the_learners_own_open_attempt_is_read(self):
        _, db = self.run_check([{'private_snapshot': snapshot()}])
        chain = db.table.return_value.select.return_value
        calls = []
        while chain.eq.call_args_list:
            calls.extend(c.args for c in chain.eq.call_args_list); chain = chain.eq.return_value
        self.assertIn(('tenant_id', 18), calls); self.assertIn(('user_id', 7), calls); self.assertIn(('status', 'in_progress'), calls)

    def test_graded_attempts_never_reveal_answers_early(self):
        with self.assertRaises(HTTPException) as failure:
            self.run_check([{'private_snapshot': snapshot(mode='graded')}])
        self.assertEqual(failure.exception.status_code, 403)

    def test_missing_attempt_question_or_option_fails_closed(self):
        for rows, option, question, status in [([], RIGHT, QUESTION, 404), ([{'private_snapshot': snapshot(kind='written')}], RIGHT, QUESTION, 404),
                                               ([{'private_snapshot': snapshot()}], RIGHT, str(uuid4()), 404), ([{'private_snapshot': snapshot()}], str(uuid4()), QUESTION, 422)]:
            with self.subTest(status=status), self.assertRaises(HTTPException) as failure:
                self.run_check(rows, option=option, question=question)
            self.assertEqual(failure.exception.status_code, status)


if __name__ == '__main__':
    unittest.main()
