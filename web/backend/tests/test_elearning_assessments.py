"""Strict assessment API boundaries reject untyped configs and caller grading."""
import unittest
from uuid import uuid4
from pydantic import ValidationError
from services.elearning_assessments_service import AssessmentCreate, QUESTION_ADAPTER, Submission

class AssessmentValidationTests(unittest.TestCase):
    def test_settings_and_question_validation(self):
        valid={'expected_revision':1,'assessment':{'title':'Check','passing_score':70},'questions':[{'type':'true_false','prompt':'True?','points':1,'config':{'correct_answer':False}}]}
        self.assertIsNone(AssessmentCreate.model_validate(valid).assessment.max_attempts)
        for settings in [{'passing_score':101},{'passing_score':float('nan')},{'max_attempts':0},{'max_attempts':True},{'required_for_completion':'true'},{'status':'unknown'},{'tenant_id':5}]:
            with self.subTest(settings=settings),self.assertRaises(ValidationError): AssessmentCreate.model_validate({**valid,'assessment':{**valid['assessment'],**settings}})
        for question in [{'type':'speaking','prompt':'Say','points':1,'config':{'max_duration_seconds':0}},{'type':'true_false','prompt':'True?','points':0,'config':{'correct_answer':True}},{'type':'true_false','prompt':'True?','points':1.001,'config':{'correct_answer':True}},{'type':'true_false','prompt':'True?','points':1,'config':{'correct_answer':'true'}}]:
            with self.subTest(question=question),self.assertRaises(ValidationError): QUESTION_ADAPTER.validate_python(question)

    def test_matching_requires_bijective_keys(self):
        ids=[str(uuid4()) for _ in range(4)]
        config={'prompts':[{'id':ids[0],'label':'A'},{'id':ids[1],'label':'B'}],'targets':[{'id':ids[2],'label':'X'},{'id':ids[3],'label':'Y'}],'correct_pairs':{ids[0]:ids[2],ids[1]:ids[3]}}
        QUESTION_ADAPTER.validate_python({'type':'matching','prompt':'Match','points':1,'config':config})
        config['correct_pairs'][ids[1]]=ids[2]
        with self.assertRaises(ValidationError): QUESTION_ADAPTER.validate_python({'type':'matching','prompt':'Match','points':1,'config':config})

    def test_submission_rejects_scores_identity_and_extra_response_fields(self):
        q=str(uuid4());Submission.model_validate({'answers':{q:{'value':True}}})
        for payload in [{'answers':{q:{'value':True,'earned_points':99}}},{'answers':{q:{'value':'true'}}},{'answers':{q:{'value':True}},'score_percentage':100},{'answers':{q:{'value':True}},'user_id':1}]:
            with self.subTest(payload=payload),self.assertRaises(ValidationError): Submission.model_validate(payload)

class HumanAssessmentValidationTests(unittest.TestCase):
    def test_subjective_responses_reject_client_scores_and_unbounded_text(self):
        q=str(uuid4())
        Submission.model_validate({'answers':{q:{'text':'An original bounded response'}}})
        Submission.model_validate({'answers':{q:{'recording_id':str(uuid4())}}})
        for response in [{'text':'A','points':10},{'recording_id':str(uuid4()),'score':100},{'text':'x'*20001},{'finished':False}]:
            with self.subTest(response_type=list(response)),self.assertRaises(ValidationError):Submission.model_validate({'answers':{q:response}})

    def test_rubric_and_recording_limits_are_strictly_bounded(self):
        base={'type':'speaking','prompt':'Explain','points':5,'config':{'rubric':'Clear explanation','max_duration_seconds':30,'max_size_bytes':100000}}
        QUESTION_ADAPTER.validate_python(base)
        for values in [{'max_duration_seconds':301},{'max_size_bytes':10485761},{'max_duration_seconds':True},{'rubric':'x'*10001},{'auto_score':True}]:
            with self.subTest(values=list(values)),self.assertRaises(ValidationError):QUESTION_ADAPTER.validate_python({**base,'config':{**base['config'],**values}})
