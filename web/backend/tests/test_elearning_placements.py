import unittest
from uuid import uuid4
from pydantic import ValidationError
from services.elearning_placements_service import PlacedAssessment,AttachAssessment,PlacementCommand
from services.elearning_assessments_service import args

class PlacementValidationTests(unittest.TestCase):
    def test_placement_models_reuse_the_typed_assessment_engine(self):
        section=uuid4();payload=PlacedAssessment.model_validate({'expected_revision':1,'section_id':section,'assessment':{'title':'Level Check','required_for_completion':True},'questions':[{'type':'true_false','prompt':'True?','points':1,'config':{'correct_answer':True}}]})
        self.assertEqual(payload.section_id,section);self.assertEqual(payload.questions[0].type,'true_false')
        self.assertIsNone(args(uuid4(),None,uuid4())['p_lesson_id'])
        for extra in [{'tenant_id':1},{'user_id':5},{'score_percentage':100},{'completed':True}]:
            with self.assertRaises(ValidationError): PlacedAssessment.model_validate({'expected_revision':1,'assessment':{'title':'Check'},**extra})
    def test_attach_and_commands_validate_identifiers_and_actions(self):
        AttachAssessment.model_validate({'expected_revision':1,'assessment_id':str(uuid4())})
        for action in ['complete','reset_attempts','force_pass']:
            with self.assertRaises(ValidationError): PlacementCommand.model_validate({'expected_revision':1,'action':action})
        with self.assertRaises(ValidationError): AttachAssessment.model_validate({'expected_revision':1,'assessment_id':'other','required_for_completion':'true'})
