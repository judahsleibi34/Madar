"""Generic objective assessment authoring and learner-safe transactional runtime."""
from typing import Annotated, Literal
from uuid import UUID
from decimal import Decimal
from fastapi import HTTPException
from pydantic import Field, StrictBool, TypeAdapter, field_validator, model_validator
from postgrest.exceptions import APIError
from database import service_supabase
from services.elearning_structure_service import Payload, Direction, Confirmation
from services.elearning_settings_service import settings_available


class AssessmentDetails(Payload):
    title: str = Field(min_length=1, max_length=120)
    instructions: str = Field(default='', max_length=10000)
    passing_score: float = Field(default=70, ge=0, le=100, strict=True, allow_inf_nan=False)
    max_attempts: int | None = Field(default=None, ge=1, le=10000, strict=True)
    required_for_completion: StrictBool = False
    status: Literal['draft','published','archived'] = 'draft'


class Option(Payload):
    id: UUID
    label: str = Field(min_length=1, max_length=2000)


class AudioPrompt(Payload):
    id: UUID
    media_id: UUID
    admin_label: str = Field(default='', max_length=120)


class ChoiceConfig(Payload):
    options: list[Option] = Field(min_length=2,max_length=20)
    correct_option_id: UUID

    @model_validator(mode='after')
    def choices(self):
        ids=[v.id for v in self.options]
        if len(set(ids))!=len(ids) or self.correct_option_id not in ids: raise ValueError('Choose exactly one valid correct option')
        return self


class BooleanConfig(Payload):
    correct_answer: StrictBool


class MatchingConfig(Payload):
    prompts: list[Option] = Field(min_length=2,max_length=50)
    targets: list[Option] = Field(min_length=2,max_length=50)
    correct_pairs: dict[UUID,UUID]

    @model_validator(mode='after')
    def pairs(self):
        left=[v.id for v in self.prompts];right=[v.id for v in self.targets]
        if len(set(left))!=len(left) or len(set(right))!=len(right) or len(left)!=len(right) or set(self.correct_pairs)!=set(left) or set(self.correct_pairs.values())!=set(right): raise ValueError('Provide at least two distinct, complete matching pairs')
        return self


class ListeningConfig(MatchingConfig):
    prompts: list[AudioPrompt] = Field(min_length=2,max_length=50)


class QuestionDetails(Payload):
    prompt: str = Field(min_length=1,max_length=10000)
    points: float = Field(default=1,gt=0,le=10000,strict=True,allow_inf_nan=False)

    @field_validator('points')
    @classmethod
    def precise_points(cls,value):
        if Decimal(str(value)).as_tuple().exponent < -2: raise ValueError('Use at most two decimal places for points')
        return value


class ChoiceQuestion(QuestionDetails):
    type: Literal['multiple_choice']
    config: ChoiceConfig


class BooleanQuestion(QuestionDetails):
    type: Literal['true_false']
    config: BooleanConfig


class MatchingQuestion(QuestionDetails):
    type: Literal['matching']
    config: MatchingConfig


class ListeningQuestion(QuestionDetails):
    type: Literal['listen_match']
    config: ListeningConfig


Question = Annotated[ChoiceQuestion | BooleanQuestion | MatchingQuestion | ListeningQuestion,Field(discriminator='type')]
QUESTION_ADAPTER=TypeAdapter(Question)


class AssessmentCreate(Payload):
    expected_revision: int = Field(ge=1,strict=True)
    assessment: AssessmentDetails
    questions: list[Question] = Field(default_factory=list,max_length=200)


class AssessmentCommand(Payload):
    action: Literal['settings','create_question','update_question','duplicate_question','reorder_question','archive_question','restore_question','delete_question','delete_assessment']
    expected_revision: int = Field(ge=1,strict=True)
    question_id: UUID | None = None
    payload: dict = Field(default_factory=dict)

    @model_validator(mode='after')
    def command(self):
        existing=self.action not in {'settings','create_question','delete_assessment'}
        if existing!=(self.question_id is not None): raise ValueError('Select the correct question')
        if self.action=='settings': parsed=AssessmentDetails.model_validate(self.payload)
        elif self.action in {'create_question','update_question'}: parsed=QUESTION_ADAPTER.validate_python(self.payload)
        elif self.action=='reorder_question': parsed=Direction.model_validate(self.payload)
        elif self.action in {'archive_question','delete_question','delete_assessment'}: parsed=Confirmation.model_validate(self.payload)
        else: parsed=Payload.model_validate(self.payload)
        self.payload=parsed.model_dump(mode='json')
        return self


class ChoiceResponse(Payload):
    option_id: UUID


class BooleanResponse(Payload):
    value: StrictBool


class MatchingResponse(Payload):
    matches: dict[UUID,UUID] = Field(min_length=2,max_length=50)


class Submission(Payload):
    answers: dict[UUID,ChoiceResponse | BooleanResponse | MatchingResponse] = Field(min_length=1,max_length=200)


def call(name,tenant_id,**args):
    if not settings_available(126): raise HTTPException(503,detail={'code':'assessment_upgrade_required','message':'Assessments require the database upgrade.'})
    try: return service_supabase.rpc(name,{'p_tenant_id':tenant_id,**args}).execute().data
    except APIError as error:
        code=error.message
        if error.code=='P0002': raise HTTPException(404,detail={'code':'assessment_not_found','message':'Assessment, question or attempt is unavailable.'}) from error
        if error.code=='P0001': raise HTTPException(409,detail={'code':code,'message':'This assessment changed. Reload before saving.'}) from error
        if error.code=='42501': raise HTTPException(403,detail={'code':code if code in {'assessment_attempt_limit','elearning_assessment_required','elearning_lesson_locked'} else 'assessment_forbidden','message':'Assessment access is unavailable or the attempt limit has been reached.'}) from error
        if error.code in {'22023','23514','23503','22P02','23502','23505'}:
            safe=code if code in {'assessment_questions_required','assessment_invalid_audio','assessment_answers_required','assessment_invalid_response','assessment_correct_option_required','assessment_question_limit'} else 'assessment_invalid'
            raise HTTPException(400,detail={'code':safe,'message':{'assessment_questions_required':'Add at least one active question before publishing.','assessment_invalid_audio':'Select valid authorized audio for every listening prompt.','assessment_answers_required':'Answer every question before submitting.','assessment_invalid_response':'Select valid answers and use each matching target once.'}.get(safe,'Check the assessment settings, questions and media references.')}) from error
        raise


def args(course,lesson,block=None):
    return {'p_course_id':str(course),'p_lesson_id':str(lesson) if lesson else None,**({'p_block_id':str(block)} if block else {})}


def author(member,course,lesson,block,preview=False):
    return call('get_elearning_assessment_preview' if preview else 'get_elearning_assessment_author',member.tenant_id,**args(course,lesson,block))


def create(member,course,lesson,payload):
    return call('create_elearning_assessment',member.tenant_id,**args(course,lesson),p_actor_id=member.user_id,p_expected_revision=payload.expected_revision,p_details=payload.assessment.model_dump(mode='json'),p_questions=[q.model_dump(mode='json') for q in payload.questions])


def manage(member,course,lesson,block,payload):
    return call('manage_elearning_assessment',member.tenant_id,**args(course,lesson,block),p_actor_id=member.user_id,p_expected_revision=payload.expected_revision,p_action=payload.action,p_question_id=str(payload.question_id) if payload.question_id else None,p_payload=payload.payload)


def runtime(member,course,lesson,block,start=False,attempt=None,payload=None):
    return call('submit_elearning_assessment_attempt' if attempt else 'start_elearning_assessment_attempt' if start else 'elearning_assessment_runtime',member.tenant_id,**args(course,lesson,block),p_user_id=member.user_id,**({'p_attempt_id':str(attempt),'p_answers':payload.model_dump(mode='json')['answers']} if attempt else {}))
