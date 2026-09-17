import copy
import json
import os
import unittest
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from routes.public_site_routes import PublicQuizFinalizeCreate, build_authorized_public_schema
from services.public_quiz_service import (
    build_attempt_payload,
    grade,
    public_form,
    validate_submission_order,
)


PRIVATE_FORM = {
    "id": "quiz-1",
    "mode": "quiz",
    "quiz": {
        "scoring": "automatic",
        "passingScore": 70,
        "totalTimeLimitSec": 60,
        "showResults": True,
        "randomizeQuestions": True,
    },
    "sections": [{
        "id": "section-1",
        "fields": [
            {"id": "q1", "type": "radio", "quizCorrectAnswer": "A", "quizPoints": 5},
            {"id": "q2", "type": "checkboxes", "correct_answer": ["B"], "quizCorrectAnswer": ["B", "C"]},
        ],
    }],
    "rubric": "secret",
}


class PublicQuizSecurityTests(unittest.TestCase):
    def test_public_form_recursively_removes_every_private_grading_key(self):
        source = copy.deepcopy(PRIVATE_FORM)
        payload = public_form(source)
        encoded = json.dumps(payload).lower()
        for forbidden in ("quizcorrectanswer", "quizpoints", "correct_answer", "rubric", "passingscore", "scoring"):
            self.assertNotIn(forbidden, encoded)
        self.assertIn("quizCorrectAnswer", json.dumps(source))

    def test_entire_publication_schema_is_redacted_not_only_forms(self):
        schema = {
            "defaultPageId": "home",
            "pages": [{"id": "home", "quizCorrectAnswer": "leaked", "settings": {"answerKey": "leaked"}}],
            "forms": [],
        }
        encoded = json.dumps(build_authorized_public_schema(schema)).lower()
        self.assertNotIn("quizcorrectanswer", encoded)
        self.assertNotIn("answerkey", encoded)

    def test_server_grades_without_trusting_forged_result_fields(self):
        result = grade(PRIVATE_FORM, {"q1": "wrong", "q2": ["B", "C"], "score": 100, "passed": True})
        self.assertEqual(result["correct"], 1)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["score"], 50)
        self.assertFalse(result["passed"])

    def test_attempt_is_pinned_to_publication_and_has_server_order(self):
        project = {"id": "00000000-0000-0000-0000-000000000001", "published_version": 8, "published_schema": {"forms": [PRIVATE_FORM]}}
        attempt = build_attempt_payload(tenant_id=7, project=project, form=PRIVATE_FORM, subject_hash="a" * 64)
        self.assertEqual(attempt["publication_version"], 8)
        self.assertEqual(set(attempt["question_order"]), {"q1", "q2"})
        self.assertIn("quizCorrectAnswer", json.dumps(attempt["private_form_snapshot"]))

    def test_foreign_question_id_is_rejected(self):
        with self.assertRaises(HTTPException):
            validate_submission_order({"question_order": ["q1"]}, {"other-test-question": "A"})

    def test_changed_question_order_is_not_accepted_from_client(self):
        # The finalize contract contains answers only; order is read from the
        # private attempt. Unknown client-supplied metadata is rejected.
        with self.assertRaises(HTTPException):
            validate_submission_order({"question_order": ["q1", "q2"]}, {"question_order": ["q2", "q1"]})

    def test_finalize_contract_rejects_forged_score_state_and_deadline(self):
        for forged in (
            {"answers": {"q1": "A"}, "score": 100},
            {"answers": {"q1": "A"}, "passed": True},
            {"answers": {"q1": "A"}, "attempt_number": 1},
            {"answers": {"q1": "A"}, "deadline": "2099-01-01T00:00:00Z"},
        ):
            with self.subTest(forged=forged), self.assertRaises(ValidationError):
                PublicQuizFinalizeCreate.model_validate(forged)

    def test_attempt_migration_serializes_limits_and_finalize_with_row_lock(self):
        local = Path(__file__).resolve().parents[1]
        configured = Path(os.getenv("MADAR_TEST_REPOSITORY_ROOT") or local)
        web_root = configured if (configured / "database/migrations").is_dir() else Path("/workspace")
        database_sql = (web_root / "database/migrations/082_create_public_quiz_attempts.sql").read_text(encoding="utf-8")
        supabase_sql = (web_root / "supabase/migrations/082_create_public_quiz_attempts.sql").read_text(encoding="utf-8")
        self.assertEqual(database_sql, supabase_sql)
        sql = " ".join(database_sql.lower().split())
        self.assertIn("pg_advisory_xact_lock", sql)
        self.assertIn("if used >= p_max_attempts", sql)
        self.assertIn("where id=p_attempt_id for update", sql)
        self.assertIn("attempt.tenant_id<>p_tenant_id", sql)
        self.assertIn("attempt.project_id<>p_project_id", sql)
        self.assertIn("attempt.publication_version<>p_publication_version", sql)
        self.assertIn("if attempt.state='completed' then return jsonb_build_object('duplicate',true", sql)
        self.assertIn("return jsonb_build_object('error','quiz_attempt_expired')", sql)
        self.assertIn("revoke all on public.public_quiz_attempts from public, anon, authenticated", sql)


if __name__ == "__main__":
    unittest.main()
