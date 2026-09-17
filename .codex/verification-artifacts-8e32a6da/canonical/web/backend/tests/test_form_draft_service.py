import unittest
from unittest.mock import patch
from uuid import uuid4

from services.form_draft_service import build_form_draft_token, parse_form_draft_token


class FormDraftTokenTests(unittest.TestCase):
    def test_signed_token_round_trip_and_tampering(self):
        draft_id = str(uuid4())
        with patch.dict("os.environ", {"FORM_DRAFT_TOKEN_SECRET": "test-secret"}):
            token = build_form_draft_token(draft_id)
            self.assertEqual(parse_form_draft_token(token), draft_id)
            replacement = "0" if token[-1] != "0" else "1"
            self.assertIsNone(parse_form_draft_token(f"{token[:-1]}{replacement}"))


if __name__ == "__main__":
    unittest.main()
